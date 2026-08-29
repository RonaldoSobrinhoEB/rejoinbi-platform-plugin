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


class RemoveFileTests(unittest.TestCase):
    def test_command_is_registered_with_expected_flags(self):
        parser = plugin.build_parser()
        sub = next(action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction")
        self.assertIn("remove-file", sub.choices)
        cmd = sub.choices["remove-file"]
        self.assertIs(cmd.get_default("func"), plugin.cmd_remove_file)
        self.assertTrue(any("--workspace" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--path" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--type" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--confirm-path" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--restart" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--yes" in opt for act in cmd._actions for opt in act.option_strings))
        self.assertTrue(any("--dry-run" in opt for act in cmd._actions for opt in act.option_strings))
        for act in cmd._actions:
            if any("--type" in opt for opt in act.option_strings):
                self.assertEqual(list(act.choices or []), ["file", "folder"])

    def test_locked_workspace_scope_and_mutating_registration(self):
        self.assertEqual(plugin.operation_scope_for_command(scoped_args("remove-file")), "workspace")
        self.assertIn("remove-file", plugin.MUTATING_COMMANDS_REQUIRING_EXPLICIT_TENANT)
        with self.assertRaisesRegex(plugin.RejoinBIError, "locked to the .workspace. operation scope"):
            plugin.ensure_operation_scope_for_command(scoped_args("remove-file", operation_scope="pages"))
        self.assertEqual(
            plugin.ensure_operation_scope_for_command(scoped_args("remove-file", operation_scope="workspace")),
            "workspace",
        )

    def test_raw_api_path_is_classified_as_workspace(self):
        self.assertEqual(plugin.api_path_operation_scope("/plataforma/api/delete-individual-item"), "workspace")

    def test_build_remove_file_plan(self):
        workspace = {"id": 17, "name": "site-b", "nome": "Site B"}
        args = argparse.Namespace(workspace="site-b", path="legado/antigo.html", type="file", name="", restart=True)
        plan = plugin.build_remove_file_plan(args, workspace)
        self.assertEqual(plan["container_id"], "17")
        self.assertEqual(plan["file_path"], "legado/antigo.html")
        self.assertEqual(plan["item_type"], "file")
        self.assertEqual(plan["item_name"], "antigo.html")
        self.assertTrue(plan["restart_container"])

    def test_plan_validates_type_and_path(self):
        workspace = {"id": 1, "name": "x"}
        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_remove_file_plan(argparse.Namespace(workspace="x", path="a", type="dir", name="", restart=False), workspace)
        with self.assertRaises(plugin.RejoinBIError):
            plugin.build_remove_file_plan(argparse.Namespace(workspace="x", path="", type="file", name="", restart=False), workspace)


if __name__ == "__main__":
    unittest.main()
