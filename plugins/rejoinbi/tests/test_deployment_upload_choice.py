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


def deploy_args(**overrides) -> argparse.Namespace:
    values = {
        "skip_upload": False,
        "upload_mode": "",
        "changed_file": [],
        "changed_target_path": [],
        "allow_database_files": False,
        "allow_sensitive_files": False,
        "replace_pages": False,
        "sync_pages": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class DeploymentUploadChoiceTests(unittest.TestCase):
    def test_deployment_requires_an_explicit_upload_choice(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "Deployment blocked before contacting the platform"):
            plugin.require_deploy_upload_mode(deploy_args())

    def test_full_upload_rejects_incremental_only_options(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "only valid with --upload-mode changed-files"):
            plugin.require_deploy_upload_mode(
                deploy_args(upload_mode="full", changed_file=["static/app.js"])
            )

    def test_changed_files_mode_requires_reviewed_file_list(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "requires one or more --changed-file"):
            plugin.require_deploy_upload_mode(deploy_args(upload_mode="changed-files"))

    def test_skip_upload_cannot_bypass_the_required_choice(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "cannot bypass the mandatory upload choice"):
            plugin.require_deploy_upload_mode(deploy_args(skip_upload=True))

    def test_incremental_files_keep_project_relative_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            changed = root / "static" / "app.js"
            changed.parent.mkdir(parents=True)
            changed.write_text("console.log('updated')", encoding="utf-8")

            entries = plugin.build_deploy_changed_upload_entries(
                deploy_args(upload_mode="changed-files", changed_file=["static/app.js"]),
                root,
            )

            self.assertEqual(entries, [(changed.resolve(), "static/app.js")])

    def test_data_confirmation_distinguishes_project_config_from_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            root.mkdir(parents=True)
            package_json = root / "package.json"
            package_json.write_text("{}", encoding="utf-8")
            data_file = root / "data" / "records.json"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("[]", encoding="utf-8")

            args = deploy_args(
                upload_mode="changed-files",
                changed_file=["package.json"],
            )
            self.assertEqual(
                plugin.confirm_sensitive_data_files(args, [(package_json, "package.json")], context="test"),
                [],
            )
            with self.assertRaisesRegex(plugin.RejoinBIError, "--allow-data-files"):
                plugin.confirm_sensitive_data_files(args, [(data_file, "data/records.json")], context="test")

            args.allow_data_files = True
            findings = plugin.confirm_sensitive_data_files(
                args,
                [(data_file, "data/records.json")],
                context="test",
            )
            self.assertEqual(findings[0]["target"], "data/records.json")

    def test_incremental_files_block_database_without_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            database = root / "data" / "production.sqlite3"
            database.parent.mkdir(parents=True)
            database.write_bytes(b"SQLite format 3\x00")

            with self.assertRaisesRegex(plugin.RejoinBIError, "Incremental deployment blocked database artifact"):
                plugin.build_deploy_changed_upload_entries(
                    deploy_args(upload_mode="changed-files", changed_file=["data/production.sqlite3"]),
                    root,
                )

            entries = plugin.build_deploy_changed_upload_entries(
                deploy_args(
                    upload_mode="changed-files",
                    changed_file=["data/production.sqlite3"],
                    allow_database_files=True,
                ),
                root,
            )
            self.assertEqual(entries, [(database.resolve(), "data/production.sqlite3")])

    def test_deploy_parser_exposes_the_choice_and_incremental_files(self):
        parser = plugin.build_parser()
        parsed = parser.parse_args([
            "deploy-manifest",
            "--manifest",
            "rejoinbi-app.json",
            "--upload-mode",
            "changed-files",
            "--changed-file",
            "static/app.js",
            "--operation-scope",
            "deployment",
        ])
        self.assertEqual(parsed.upload_mode, "changed-files")
        self.assertEqual(parsed.changed_file, ["static/app.js"])
        self.assertEqual(parsed.operation_scope, "deployment")


if __name__ == "__main__":
    unittest.main()
