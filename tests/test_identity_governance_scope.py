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
    values = {
        "command": command,
        "identity_scope": False,
        "yes": False,
        "path": "",
        "include_identity": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class IdentityGovernanceScopeTests(unittest.TestCase):
    def test_identity_reads_are_blocked_without_explicit_scope(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(scoped_args("users"))
        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(scoped_args("setores"))

    def test_identity_reads_are_allowed_only_after_opt_in(self):
        plugin.ensure_identity_scope_for_command(scoped_args("groups", identity_scope=True))

    def test_identity_writes_require_scope_and_yes(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(scoped_args("update-user", yes=True))
        with self.assertRaisesRegex(plugin.RejoinBIError, "both --identity-scope and --yes"):
            plugin.ensure_identity_scope_for_command(scoped_args("update-user", identity_scope=True))
        plugin.ensure_identity_scope_for_command(
            scoped_args("update-user", identity_scope=True, yes=True)
        )

    def test_unrelated_workspace_work_does_not_require_identity_scope(self):
        plugin.ensure_identity_scope_for_command(scoped_args("upload-folder-select"))
        plugin.ensure_identity_scope_for_command(scoped_args("workspaceall"))

    def test_raw_identity_endpoints_cannot_bypass_scope(self):
        args = scoped_args("api-get", path="/plataforma/api/users")
        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(args)

        args = scoped_args(
            "api-send",
            path="/plataforma/api/update-permissions",
            identity_scope=True,
        )
        with self.assertRaisesRegex(plugin.RejoinBIError, "both --identity-scope and --yes"):
            plugin.ensure_identity_scope_for_command(args)

        plugin.ensure_identity_scope_for_command(
            scoped_args(
                "api-send",
                path="/plataforma/api/update-permissions",
                identity_scope=True,
                yes=True,
            )
        )

    def test_indirect_identity_selectors_are_scoped_without_blocking_other_actions(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(
                scoped_args("workspace-notification", action="users")
            )
        plugin.ensure_identity_scope_for_command(
            scoped_args("workspace-notification", action="config")
        )

        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(
                scoped_args("codex-keys", action="users")
            )
        plugin.ensure_identity_scope_for_command(
            scoped_args("codex-keys", action="list")
        )

        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(
                scoped_args("api-get", path="plataforma/api/sleep-manager/users-online")
            )

    def test_smoke_admin_skips_identity_unless_both_flags_are_given(self):
        default = scoped_args("smoke-admin")
        self.assertFalse(plugin.command_uses_identity_governance(default))
        plugin.ensure_identity_scope_for_command(default)

        requested = scoped_args("smoke-admin", include_identity=True)
        self.assertTrue(plugin.command_uses_identity_governance(requested))
        with self.assertRaisesRegex(plugin.RejoinBIError, "Identity governance is disabled"):
            plugin.ensure_identity_scope_for_command(requested)

        plugin.ensure_identity_scope_for_command(
            scoped_args("smoke-admin", include_identity=True, identity_scope=True)
        )

    def test_parser_exposes_identity_scope_only_for_identity_commands(self):
        parser = plugin.build_parser()
        users = parser.parse_args(["users", "--identity-scope"])
        self.assertTrue(users.identity_scope)

        smoke = parser.parse_args(
            ["smoke-admin", "--include-identity", "--identity-scope"]
        )
        self.assertTrue(smoke.include_identity)
        self.assertTrue(smoke.identity_scope)

    def test_target_confirmation_requires_resolved_identity(self):
        args = argparse.Namespace(confirm_user="wrong@example.com")
        with self.assertRaisesRegex(plugin.RejoinBIError, "--confirm-user"):
            plugin.require_identity_target_confirmation(
                args,
                "confirm_user",
                "a user",
                ["u-1", "user@example.com"],
            )

        args.confirm_user = "user@example.com"
        plugin.require_identity_target_confirmation(
            args,
            "confirm_user",
            "a user",
            ["u-1", "user@example.com"],
        )


if __name__ == "__main__":
    unittest.main()
