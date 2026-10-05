from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "rejoinbi.py"
SPEC = importlib.util.spec_from_file_location("rejoinbi_upload_path_contract", SCRIPT)
assert SPEC and SPEC.loader
plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin)


def selected_args(files: list[Path], **overrides) -> argparse.Namespace:
    values = {
        "files": [str(path) for path in files],
        "source_root": "",
        "preserve_paths": False,
        "folder": "",
        "map": [],
        "target_path": [],
        "allow_root_drop": False,
        "allow_sensitive_files": False,
        "allow_database_files": False,
        "allow_data_files": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def write_file(root: Path, relative: str, content: bytes = b"print('path contract')\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path.resolve()


class FakeApplyClient:
    """Record the final incremental apply request without contacting a platform."""

    base_url = "https://path-contract.invalid"

    def __init__(self, remote_files: dict[str, bytes] | None = None):
        self.calls: list[tuple[str, str, dict]] = []
        self.remote_files = remote_files or {}

    def request(self, method: str, path: str, **kwargs):
        self.calls.append((method, path, kwargs))
        if method == "POST" and path == "/plataforma/api/upload-apply-files":
            return {"success": True, "files": kwargs["json"]["files"]}, None
        if method == "GET" and path == "/plataforma/api/workspace-file":
            target = kwargs["params"]["path"]
            if target not in self.remote_files:
                return {"success": False, "path": target}, None
            return {
                "success": True,
                "path": target,
                "sha256": hashlib.sha256(self.remote_files[target]).hexdigest(),
            }, None
        raise AssertionError(f"Unexpected platform request: {method} {path}")


class SelectedUploadPathContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        self.root.mkdir()
        self.source = write_file(self.root, "services/foo.py")

    def test_single_nested_file_keeps_its_project_relative_path(self):
        entries = plugin.build_individual_upload_entries(
            selected_args([self.source], source_root=str(self.root))
        )

        self.assertEqual(entries, [(self.source, "services/foo.py")])

    def test_explicit_destination_folder_prefixes_the_preserved_path(self):
        entries = plugin.build_individual_upload_entries(
            selected_args([self.source], source_root=str(self.root), folder="release")
        )

        self.assertEqual(entries, [(self.source, "release/services/foo.py")])

    def test_source_root_allows_a_file_that_actually_belongs_at_project_root(self):
        root_file = write_file(self.root, "app.py")

        entries = plugin.build_individual_upload_entries(
            selected_args([root_file], source_root=str(self.root))
        )

        self.assertEqual(entries, [(root_file, "app.py")])

    def test_upload_without_an_explicit_root_or_destination_is_rejected(self):
        for allow_root_drop in (False, True):
            with self.subTest(allow_root_drop=allow_root_drop):
                with self.assertRaises(plugin.RejoinBIError):
                    plugin.build_individual_upload_entries(
                        selected_args([self.source], allow_root_drop=allow_root_drop)
                    )

    def test_preserve_paths_does_not_infer_a_root_from_one_file(self):
        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_individual_upload_entries(
                selected_args([self.source], preserve_paths=True)
            )

    def test_preserve_paths_does_not_infer_a_common_root_from_sibling_files(self):
        sibling = write_file(self.root, "services/bar.py")

        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_individual_upload_entries(
                selected_args([self.source, sibling], preserve_paths=True)
            )

    def test_exact_target_without_source_root_is_an_explicit_destination(self):
        entries = plugin.build_individual_upload_entries(
            selected_args(
                [self.source],
                target_path=[f"{self.source}=services/foo.py"],
            )
        )

        self.assertEqual(entries, [(self.source, "services/foo.py")])

    def test_exact_target_makes_preserve_paths_safe_without_an_inferred_root(self):
        entries = plugin.build_individual_upload_entries(
            selected_args(
                [self.source],
                preserve_paths=True,
                target_path=[f"{self.source}=services/foo.py"],
            )
        )

        self.assertEqual(entries, [(self.source, "services/foo.py")])

    def test_explicit_folder_without_source_root_is_an_explicit_destination(self):
        entries = plugin.build_individual_upload_entries(
            selected_args([self.source], folder="services")
        )

        self.assertEqual(entries, [(self.source, "services/foo.py")])

    def test_folder_mapping_without_source_root_is_an_explicit_destination(self):
        entries = plugin.build_individual_upload_entries(
            selected_args([self.source], map=[f"{self.source}=services"])
        )

        self.assertEqual(entries, [(self.source, "services/foo.py")])

    def test_a_partially_mapped_selection_cannot_flatten_the_unmapped_file(self):
        sibling = write_file(self.root, "services/bar.py")

        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_individual_upload_entries(
                selected_args(
                    [self.source, sibling],
                    target_path=[f"{self.source}=services/foo.py"],
                )
            )

    def test_nested_source_cannot_be_mapped_to_workspace_root_without_opt_in(self):
        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_individual_upload_entries(
                selected_args(
                    [self.source],
                    source_root=str(self.root),
                    target_path=[f"{self.source}=foo.py"],
                )
            )

    def test_allow_root_drop_permits_an_explicit_root_target(self):
        entries = plugin.build_individual_upload_entries(
            selected_args(
                [self.source],
                source_root=str(self.root),
                target_path=[f"{self.source}=foo.py"],
                allow_root_drop=True,
            )
        )

        self.assertEqual(entries, [(self.source, "foo.py")])

    def test_exact_mapping_and_root_drop_opt_in_cannot_bypass_source_containment(self):
        outside = write_file(Path(self.temporary.name), "elsewhere/outside.py")

        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_individual_upload_entries(
                selected_args(
                    [outside],
                    source_root=str(self.root),
                    target_path=[f"{outside}=outside.py"],
                    allow_root_drop=True,
                )
            )

    def test_same_named_files_in_distinct_folders_remain_distinct(self):
        other = write_file(self.root, "utilities/foo.py", b"print('utility')\n")

        entries = plugin.build_individual_upload_entries(
            selected_args([self.source, other], source_root=str(self.root))
        )

        self.assertEqual(
            entries,
            [(self.source, "services/foo.py"), (other, "utilities/foo.py")],
        )

    def test_basename_folder_mapping_is_rejected_when_two_sources_share_that_name(self):
        other = write_file(self.root, "utilities/foo.py")

        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_individual_upload_entries(
                selected_args(
                    [self.source, other],
                    source_root=str(self.root),
                    map=["foo.py=release"],
                )
            )

    def test_exact_source_mappings_disambiguate_same_named_files(self):
        other = write_file(self.root, "utilities/foo.py")

        entries = plugin.build_individual_upload_entries(
            selected_args(
                [self.source, other],
                source_root=str(self.root),
                target_path=[
                    f"{self.source}=release/services/foo.py",
                    f"{other}=release/utilities/foo.py",
                ],
            )
        )

        self.assertEqual(
            entries,
            [
                (self.source, "release/services/foo.py"),
                (other, "release/utilities/foo.py"),
            ],
        )

    def test_unused_mapping_typo_is_rejected_instead_of_ignored(self):
        for option in ("map", "target_path"):
            with self.subTest(option=option):
                mapping = "fop.py=release" if option == "map" else "fop.py=release/foo.py"
                with self.assertRaises(plugin.RejoinBIError):
                    plugin.build_individual_upload_entries(
                        selected_args(
                            [self.source],
                            source_root=str(self.root),
                            **{option: [mapping]},
                        )
                    )

    def test_destinations_cannot_escape_the_workspace_app_directory(self):
        invalid_targets = [
            "../foo.py",
            "services/../../foo.py",
            "/services/foo.py",
            r"C:\workspace\foo.py",
            r"\\server\share\foo.py",
        ]
        for target in invalid_targets:
            for option in ("folder", "map", "target_path"):
                with self.subTest(target=target, option=option):
                    override = target if option == "folder" else [f"{self.source}={target}"]
                    with self.assertRaises(plugin.RejoinBIError):
                        plugin.build_individual_upload_entries(
                            selected_args(
                                [self.source],
                                source_root=str(self.root),
                                allow_root_drop=True,
                                **{option: override},
                            )
                        )

    def test_distinct_sources_cannot_claim_the_same_case_insensitive_target(self):
        other = write_file(self.root, "utilities/bar.py")

        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_individual_upload_entries(
                selected_args(
                    [self.source, other],
                    source_root=str(self.root),
                    target_path=[
                        f"{self.source}=services/foo.py",
                        f"{other}=SERVICES/FOO.py",
                    ],
                )
            )


class ChangedFilePathContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "project"
        self.source = write_file(self.root, "services/foo.py")

    def changed_args(self, **overrides) -> argparse.Namespace:
        values = {
            "changed_file": ["services/foo.py"],
            "changed_target_path": [],
            "allow_root_drop": False,
            "allow_sensitive_files": False,
            "allow_database_files": False,
            "allow_data_files": False,
            "dry_run": True,
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_incremental_mapping_cannot_drop_a_nested_file_at_workspace_root(self):
        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_deploy_changed_upload_entries(
                self.changed_args(changed_target_path=["services/foo.py=foo.py"]),
                self.root,
            )

    def test_incremental_root_drop_requires_and_accepts_explicit_opt_in(self):
        entries = plugin.build_deploy_changed_upload_entries(
            self.changed_args(
                changed_target_path=["services/foo.py=foo.py"], allow_root_drop=True,
            ),
            self.root,
        )

        self.assertEqual(entries, [(self.source, "foo.py")])

    def test_incremental_mapping_cannot_admit_a_source_outside_project_root(self):
        outside = write_file(Path(self.temporary.name), "outside.py")

        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_deploy_changed_upload_entries(
                self.changed_args(
                    changed_file=[str(outside)],
                    changed_target_path=[f"{outside}=services/outside.py"],
                    allow_root_drop=True,
                ),
                self.root,
            )

    def test_incremental_mapping_rejects_an_unused_source_typo(self):
        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_deploy_changed_upload_entries(
                self.changed_args(changed_target_path=["services/fop.py=services/foo.py"]),
                self.root,
            )

    def test_incremental_same_named_files_keep_distinct_project_paths(self):
        other = write_file(self.root, "utilities/foo.py")

        entries = plugin.build_deploy_changed_upload_entries(
            self.changed_args(changed_file=["services/foo.py", "utilities/foo.py"]),
            self.root,
        )

        self.assertEqual(entries, [(self.source, "services/foo.py"), (other, "utilities/foo.py")])


class UploadPathHandlerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "project"
        self.root.mkdir()
        self.source = write_file(self.root, "services/foo.py", b"# service\r\nVALUE = 7\n")
        self.entrypoint = write_file(self.root, "app.py", b"from services.foo import VALUE\n")
        self.manifest_path = self.directory / "rejoinbi-app.json"
        self.manifest_path.write_text(
            json.dumps({
                "app_root": "project",
                "workspace": {"name": "Path Regression"},
                "pages": [{"id": "path-regression", "name": "Regression", "file": "app.py"}],
            }),
            encoding="utf-8",
        )

    def parse(self, arguments: list[str]) -> argparse.Namespace:
        return plugin.build_parser().parse_args(arguments)

    def run_local_plan(self, arguments: list[str]) -> dict:
        stdout = io.StringIO()
        with patch.object(
            plugin,
            "make_client",
            side_effect=AssertionError("A local upload preview must not create a platform client"),
        ) as make_client:
            with contextlib.redirect_stdout(stdout):
                args = self.parse(arguments)
                self.assertEqual(args.func(args), 0)
            make_client.assert_not_called()
        return json.loads(stdout.getvalue())

    def assert_plan(self, plan: dict, entries: list[tuple[Path, str]]) -> None:
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["destination_base"], "workspace/app")
        files = {row["target"]: row for row in plan["files"]}
        self.assertEqual(len(plan["files"]), len(entries))
        self.assertEqual(set(files), {target for _, target in entries})
        for source, target in entries:
            with self.subTest(target=target):
                row = files[target]
                self.assertEqual(Path(row["source"]).resolve(), source)
                content = source.read_bytes()
                self.assertEqual(row["size"], len(content))
                self.assertEqual(row["sha256"], hashlib.sha256(content).hexdigest())

    def test_selected_upload_dry_run_prints_exact_destinations_without_authentication(self):
        plan = self.run_local_plan([
            "upload-files", "--workspace", "Path Regression",
            "--files", str(self.source), "--source-root", str(self.root),
            "--workspace-password", "fake-workspace-password", "--dry-run",
        ])

        self.assert_plan(plan, [(self.source, "services/foo.py")])

    def test_folder_upload_uses_its_explicit_path_as_root_in_a_local_preview(self):
        plan = self.run_local_plan([
            "upload-folder-select", "--workspace", "Path Regression",
            "--path", str(self.root), "--selected-file", "app.py", "--dry-run",
        ])

        self.assert_plan(plan, [
            (self.entrypoint, "app.py"),
            (self.source, "services/foo.py"),
        ])

    def test_full_manifest_deployment_is_previewable_without_authentication(self):
        plan = self.run_local_plan([
            "deploy-manifest", "--manifest", str(self.manifest_path),
            "--upload-mode", "full", "--dry-run",
        ])

        self.assert_plan(plan, [
            (self.entrypoint, "app.py"),
            (self.source, "services/foo.py"),
        ])

    def test_changed_file_deployment_preview_preserves_manifest_app_root_paths(self):
        plan = self.run_local_plan([
            "deploy-manifest", "--manifest", str(self.manifest_path),
            "--upload-mode", "changed-files", "--changed-file", "services/foo.py",
            "--dry-run",
        ])

        self.assert_plan(plan, [(self.source, "services/foo.py")])

    def test_each_upload_command_can_save_the_same_plan_it_prints(self):
        commands = [
            [
                "upload-files", "--workspace", "Path Regression",
                "--files", str(self.source), "--source-root", str(self.root),
            ],
            [
                "upload-folder-select", "--workspace", "Path Regression",
                "--path", str(self.root), "--selected-file", "app.py",
            ],
            [
                "deploy-manifest", "--manifest", str(self.manifest_path),
                "--upload-mode", "full",
            ],
            [
                "deploy-manifest", "--manifest", str(self.manifest_path),
                "--upload-mode", "changed-files", "--changed-file", "services/foo.py",
            ],
        ]
        for index, command in enumerate(commands):
            with self.subTest(command=command[0], upload_mode=command[-1]):
                plan_file = self.directory / f"plan-{index}.json"
                plan = self.run_local_plan(command + ["--dry-run", "--plan-output", str(plan_file)])
                self.assertEqual(json.loads(plan_file.read_text(encoding="utf-8")), plan)

    def test_plan_output_inside_upload_root_is_rejected_before_authentication(self):
        commands = [
            [
                "upload-files", "--workspace", "Path Regression",
                "--files", str(self.source), "--source-root", str(self.root),
            ],
            [
                "upload-folder-select", "--workspace", "Path Regression",
                "--path", str(self.root),
            ],
            [
                "deploy-manifest", "--manifest", str(self.manifest_path),
                "--upload-mode", "full",
            ],
        ]
        plan_file = self.root / "upload-preview.json"
        for command in commands:
            with self.subTest(command=command[0]):
                args = self.parse(command + ["--dry-run", "--plan-output", str(plan_file)])
                with patch.object(
                    plugin, "make_client", side_effect=AssertionError("An unsafe plan output must fail locally")
                ) as make_client:
                    with self.assertRaises(plugin.RejoinBIError):
                        args.func(args)
                    make_client.assert_not_called()
                self.assertFalse(plan_file.exists())

    def test_reviewed_plan_token_rejects_changed_bytes_destinations_workspace_or_tenant(self):
        command = [
            "--tenant", "path-contract.rejoinbi.com.br",
            "upload-files", "--workspace", "Path Regression",
            "--files", str(self.source), "--source-root", str(self.root),
        ]
        plan = self.run_local_plan(command + ["--dry-run"])
        original_content = self.source.read_bytes()
        for scenario in ("bytes", "destination", "workspace", "tenant"):
            with self.subTest(scenario=scenario):
                self.source.write_bytes(original_content)
                changed_command = list(command)
                if scenario == "bytes":
                    self.source.write_bytes(b"# modified since the reviewed plan\n")
                elif scenario == "destination":
                    changed_command += ["--target-path", f"{self.source}=utilities/foo.py"]
                elif scenario == "workspace":
                    changed_command[changed_command.index("Path Regression")] = "Other Workspace"
                else:
                    changed_command[1] = "other-platform.rejoinbi.com.br"
                args = self.parse(changed_command + ["--expected-plan-sha256", plan["plan_sha256"]])
                with patch.object(
                    plugin, "make_client", side_effect=AssertionError("A stale reviewed plan must fail locally")
                ) as make_client:
                    with self.assertRaises(plugin.RejoinBIError):
                        args.func(args)
                    make_client.assert_not_called()

    def test_matching_reviewed_plan_token_is_stable_between_preview_and_upload(self):
        command = [
            "upload-files", "--workspace", "Path Regression",
            "--files", str(self.source), "--source-root", str(self.root),
        ]
        plan_file = self.directory / "reviewed-upload.json"
        plan = self.run_local_plan(command + ["--dry-run", "--plan-output", str(plan_file)])
        args = self.parse(command + ["--expected-plan-sha256", plan["plan_sha256"]])
        client = FakeApplyClient()
        workspace = {"id": 59, "name": "Path Regression"}
        uploaded = {
            "files": [{"path": "services/foo.py"}],
            "summary": {"session_id": "path-contract-session", "uploaded_files": 1},
        }

        with patch.object(plugin, "make_client", return_value=client) as make_client:
            with patch.object(plugin, "resolve_workspace", return_value=workspace):
                with patch.object(plugin, "upload_entries_chunked", return_value=uploaded):
                    with patch.object(plugin, "print_payload") as printed:
                        self.assertEqual(args.func(args), 0)

        make_client.assert_called_once()
        self.assertEqual(printed.call_args.args[0]["plan"]["plan_sha256"], plan["plan_sha256"])

    def test_invalid_selected_path_contract_is_rejected_before_client_creation(self):
        args = self.parse([
            "upload-files", "--workspace", "Path Regression", "--files", str(self.source),
        ])

        with patch.object(
            plugin, "make_client", side_effect=AssertionError("Invalid paths must fail locally")
        ) as make_client:
            with self.assertRaises(plugin.RejoinBIError):
                args.func(args)
            make_client.assert_not_called()

    def test_selected_upload_preserves_the_target_in_both_chunk_and_apply_requests(self):
        args = self.parse([
            "upload-files", "--workspace", "Path Regression",
            "--files", str(self.source), "--source-root", str(self.root),
        ])
        client = FakeApplyClient()
        workspace = {"id": 59, "name": "Path Regression"}
        uploaded = {
            "files": [{"path": "services/foo.py"}],
            "summary": {"session_id": "path-contract-session", "uploaded_files": 1},
        }

        with patch.object(plugin, "make_client", return_value=client):
            with patch.object(plugin, "resolve_workspace", return_value=workspace):
                with patch.object(plugin, "upload_entries_chunked", return_value=uploaded) as upload:
                    with patch.object(plugin, "print_payload"):
                        self.assertEqual(args.func(args), 0)

        self.assertEqual(upload.call_args.args[2], [(self.source, "services/foo.py")])
        self.assertEqual(len(client.calls), 1)
        method, endpoint, kwargs = client.calls[0]
        self.assertEqual((method, endpoint), ("POST", "/plataforma/api/upload-apply-files"))
        self.assertEqual(kwargs["json"]["container_id"], 59)
        self.assertEqual(kwargs["json"]["files"], ["services/foo.py"])

    def test_upload_verification_reads_the_exact_nested_target_after_apply(self):
        args = self.parse([
            "upload-files", "--workspace", "Path Regression",
            "--files", str(self.source), "--source-root", str(self.root), "--verify-upload",
        ])
        client = FakeApplyClient({"services/foo.py": self.source.read_bytes()})
        workspace = {"id": 59, "name": "Path Regression"}
        uploaded = {
            "files": [{"path": "services/foo.py"}],
            "summary": {"session_id": "path-contract-session", "uploaded_files": 1},
        }

        with patch.object(plugin, "make_client", return_value=client):
            with patch.object(plugin, "resolve_workspace", return_value=workspace):
                with patch.object(plugin, "upload_entries_chunked", return_value=uploaded):
                    with patch.object(plugin, "print_payload"):
                        self.assertEqual(args.func(args), 0)

        self.assertEqual([path for _, path, _ in client.calls], [
            "/plataforma/api/upload-apply-files", "/plataforma/api/workspace-file",
        ])
        self.assertEqual(client.calls[1][2]["params"], {"container_id": 59, "path": "services/foo.py"})

    def test_remote_hash_mismatch_stops_before_restart(self):
        args = self.parse([
            "upload-files", "--workspace", "Path Regression",
            "--files", str(self.source), "--source-root", str(self.root),
            "--verify-upload", "--restart",
        ])
        client = FakeApplyClient({"services/foo.py": b"# incorrect remote content\n"})
        workspace = {"id": 59, "name": "Path Regression"}
        uploaded = {
            "files": [{"path": "services/foo.py"}],
            "summary": {"session_id": "path-contract-session", "uploaded_files": 1},
        }

        with patch.object(plugin, "make_client", return_value=client):
            with patch.object(plugin, "resolve_workspace", return_value=workspace):
                with patch.object(plugin, "upload_entries_chunked", return_value=uploaded):
                    with self.assertRaises(plugin.RejoinBIError):
                        args.func(args)

        self.assertFalse(any(path.endswith("/restart") for _, path, _ in client.calls))

    def test_skipped_files_are_neither_applied_nor_reported_as_verified(self):
        args = self.parse([
            "upload-files", "--workspace", "Path Regression",
            "--files", str(self.source), str(self.entrypoint), "--source-root", str(self.root),
            "--verify-upload", "--on-file-error", "skip",
        ])
        client = FakeApplyClient({"services/foo.py": self.source.read_bytes()})
        workspace = {"id": 59, "name": "Path Regression"}
        uploaded = {
            "files": [{"path": "services/foo.py"}],
            "summary": {
                "session_id": "path-contract-session", "uploaded_files": 1, "skipped_files": ["app.py"],
            },
        }

        with patch.object(plugin, "make_client", return_value=client):
            with patch.object(plugin, "resolve_workspace", return_value=workspace):
                with patch.object(plugin, "upload_entries_chunked", return_value=uploaded):
                    with patch.object(plugin, "print_payload"):
                        self.assertEqual(args.func(args), 0)

        self.assertEqual(client.calls[0][2]["json"]["files"], ["services/foo.py"])
        verified_paths = [kwargs["params"]["path"] for method, _, kwargs in client.calls if method == "GET"]
        self.assertEqual(verified_paths, ["services/foo.py"])


if __name__ == "__main__":
    unittest.main()
