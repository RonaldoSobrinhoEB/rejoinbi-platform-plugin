from __future__ import annotations

import argparse
import importlib.util
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


def scoped_args(command: str, **overrides) -> argparse.Namespace:
    values = {"command": command, "identity_scope": False, "yes": False, "path": "", "confirm_api_path": "", "operation_scope": ""}
    values.update(overrides)
    return argparse.Namespace(**values)


class WorkspaceFileReadTests(unittest.TestCase):
    def test_command_is_registered_with_list_and_read_actions(self):
        parser = plugin.build_parser()
        sub = next(action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction")
        self.assertIn("workspace-file", sub.choices)
        cmd = sub.choices["workspace-file"]
        self.assertIs(cmd.get_default("func"), plugin.cmd_workspace_file)
        action = next(act for act in cmd._actions if act.dest == "action")
        self.assertEqual(list(action.choices or []), ["list", "read"])
        self.assertTrue(any("--workspace" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--path" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--folder" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--raw" in opt for act in cmd._actions for opt in act.option_strings))

    def test_locked_to_workspace_scope_and_not_mutating(self):
        self.assertEqual(plugin.operation_scope_for_command(scoped_args("workspace-file")), "workspace")
        self.assertNotIn("workspace-file", plugin.MUTATING_COMMANDS_REQUIRING_EXPLICIT_TENANT)
        with self.assertRaisesRegex(plugin.RejoinBIError, "locked to the .workspace. operation scope"):
            plugin.ensure_operation_scope_for_command(scoped_args("workspace-file", operation_scope="pages"))
        self.assertEqual(
            plugin.ensure_operation_scope_for_command(scoped_args("workspace-file", operation_scope="workspace")),
            "workspace",
        )

    def test_workspace_file_endpoint_is_not_identity(self):
        self.assertEqual(plugin.api_path_operation_scope("/plataforma/api/workspace-file"), "workspace")

    def test_parser_parses_read_and_list_subcommands(self):
        parser = plugin.build_parser()
        read_args = parser.parse_args(["workspace-file", "read", "--workspace", "12", "--path", "app.py", "--raw"])
        self.assertEqual(read_args.action, "read")
        self.assertEqual(read_args.workspace, "12")
        self.assertEqual(read_args.path, "app.py")
        self.assertTrue(read_args.raw)
        list_args = parser.parse_args(["workspace-file", "list", "--workspace", "12", "--folder", "static"])
        self.assertEqual(list_args.action, "list")
        self.assertEqual(list_args.folder, "static")

    def test_workspace_file_handler_requires_path_for_read(self):
        # A read without --path must fail before any network call.
        from unittest import mock
        client = mock.MagicMock()
        with mock.patch.object(plugin, "make_client", return_value=client):
            with mock.patch.object(plugin, "resolve_workspace", return_value={"id": 12, "name": "site-b"}):
                with self.assertRaises(plugin.RejoinBIError):
                    plugin.cmd_workspace_file(scoped_args("workspace-file", action="read", workspace="site-b", path="", raw=True, folder="", json=True))
        # The platform must never be contacted when --path is missing.
        client.request.assert_not_called()


if __name__ == "__main__":
    unittest.main()
