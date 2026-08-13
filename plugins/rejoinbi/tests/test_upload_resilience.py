from __future__ import annotations

import argparse
import importlib.util
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
if not (PLUGIN_ROOT / "scripts").is_dir():
    PLUGIN_ROOT = PLUGIN_ROOT / "plugins" / "rejoinbi"
SCRIPT = PLUGIN_ROOT / "scripts" / "rejoinbi.py"
SPEC = importlib.util.spec_from_file_location("rejoinbi_plugin", SCRIPT)
assert SPEC and SPEC.loader
plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin)


class FakeUploadClient:
    def __init__(
        self,
        *,
        base_url: str,
        fail_paths: set[str] | None = None,
        finish_status_failures: int = 0,
    ):
        self.base_url = base_url
        self.fail_paths = fail_paths or set()
        self.finish_status_failures = finish_status_failures
        self.calls: list[tuple[str, str, dict]] = []
        self.session_id = "c1d9cc97-02a5-470a-987f-7e911a781b9b"

    def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if path == "/plataforma/api/upload-init":
            return {"success": True, "session_id": self.session_id, "chunk_size": 1024 * 1024}, None
        if path.startswith("/plataforma/api/upload-session-status?"):
            return {"success": True, "files": [], "skipped_files": []}, None
        if path == "/plataforma/api/upload-chunk":
            relative = kwargs["data"]["rel_path"]
            if relative in self.fail_paths:
                raise plugin.RejoinBIError("POST /plataforma/api/upload-chunk failed with HTTP 502: gateway")
            return {"success": True}, None
        if path == "/plataforma/api/upload-skip-file":
            return {"success": True}, None
        if path == "/plataforma/api/upload-cancel":
            return {"success": True}, None
        if path == "/plataforma/api/upload-finish":
            return {"success": True, "status": "processing"}, None
        if path.startswith("/plataforma/api/upload-finish-status?"):
            if self.finish_status_failures:
                self.finish_status_failures -= 1
                raise plugin.RejoinBIError("GET /plataforma/api/upload-finish-status failed with HTTP 502: gateway")
            return {
                "success": True,
                "status": "completed",
                "result": {"success": True, "files": [{"path": "app.py"}]},
            }, None
        raise AssertionError(f"Unexpected request: {method} {path}")

    def keep_session_alive(self, *, force: bool = False) -> None:
        return None


class UploadResilienceTests(unittest.TestCase):
    def test_selected_files_preserve_relative_folders(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            static = root / "static" / "app.js"
            template = root / "templates" / "index.html"
            static.parent.mkdir(parents=True)
            template.parent.mkdir(parents=True)
            static.write_text("console.log('ok')", encoding="utf-8")
            template.write_text("<html></html>", encoding="utf-8")
            args = argparse.Namespace(
                files=[str(static), str(template)],
                allow_sensitive_files=False,
                source_root=str(root),
                preserve_paths=False,
                map=[],
                target_path=[],
                folder="",
            )

            entries = plugin.build_individual_upload_entries(args)

            self.assertEqual([target for _, target in entries], ["static/app.js", "templates/index.html"])

    def test_resume_status_includes_workspace_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "resume.txt"
            path.write_text("resume", encoding="utf-8")
            workspace = {"id": 41, "name": "test"}
            base_url = f"https://resume-{Path(temporary).name}.rejoinbi.com.br"
            failing = FakeUploadClient(base_url=base_url, fail_paths={"resume.txt"})
            with self.assertRaises(plugin.RejoinBIError):
                plugin.upload_entries_chunked(
                    failing,
                    workspace,
                    [(path, "resume.txt")],
                    max_retries=1,
                    on_file_error="fail",
                )

            resumed = FakeUploadClient(base_url=base_url)
            plugin.upload_entries_chunked(
                resumed,
                workspace,
                [(path, "resume.txt")],
                max_retries=1,
                on_file_error="fail",
            )

            status_calls = [call for call in resumed.calls if call[1].startswith("/plataforma/api/upload-session-status?")]
            self.assertEqual(len(status_calls), 1)
            self.assertIn("container_id=41", status_calls[0][1])

    def test_skip_only_discards_failed_file_from_current_session(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad = root / "bad.txt"
            good = root / "good.txt"
            bad.write_text("bad", encoding="utf-8")
            good.write_text("good", encoding="utf-8")
            client = FakeUploadClient(
                base_url=f"https://skip-{root.name}.rejoinbi.com.br",
                fail_paths={"bad.txt"},
            )

            result = plugin.upload_entries_chunked(
                client,
                {"id": 42, "name": "test"},
                [(bad, "bad.txt"), (good, "good.txt")],
                max_retries=1,
                on_file_error="skip",
            )

            self.assertEqual(result["summary"]["skipped_files"], ["bad.txt"])
            self.assertEqual(result["summary"]["uploaded_files"], 1)
            self.assertTrue(any(path == "/plataforma/api/upload-skip-file" for _, path, _ in client.calls))

    def test_waits_for_server_finalization_before_reporting_upload_complete(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "app.py"
            path.write_text("print('ok')", encoding="utf-8")
            client = FakeUploadClient(base_url=f"https://finish-{Path(temporary).name}.rejoinbi.com.br")

            result = plugin.upload_entries_chunked(
                client,
                {"id": 57, "name": "test"},
                [(path, "app.py")],
                max_retries=1,
                on_file_error="fail",
            )

            called_paths = [path for _, path, _ in client.calls]
            self.assertIn("/plataforma/api/upload-finish", called_paths)
            self.assertTrue(any(path.startswith("/plataforma/api/upload-finish-status?") for path in called_paths))
            self.assertEqual(result["summary"]["finalization"]["files"][0]["path"], "app.py")

    def test_finalization_status_retries_a_transient_gateway_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "app.py"
            path.write_text("print('ok')", encoding="utf-8")
            client = FakeUploadClient(
                base_url=f"https://retry-finish-{Path(temporary).name}.rejoinbi.com.br",
                finish_status_failures=1,
            )

            result = plugin.upload_entries_chunked(
                client,
                {"id": 58, "name": "test"},
                [(path, "app.py")],
                max_retries=1,
                on_file_error="fail",
            )

            self.assertEqual(result["summary"]["finalization"]["files"][0]["path"], "app.py")
            finish_status_calls = [path for _, path, _ in client.calls if path.startswith("/plataforma/api/upload-finish-status?")]
            self.assertEqual(len(finish_status_calls), 2)


if __name__ == "__main__":
    unittest.main()
