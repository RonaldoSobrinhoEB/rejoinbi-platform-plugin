from __future__ import annotations

import argparse
import importlib.util
import inspect
import io
import unittest
from contextlib import redirect_stderr
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
        "confirm_api_path": "",
        "operation_scope": "",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class IdentityGovernanceScopeTests(unittest.TestCase):
    def test_profile_hierarchy_is_explicit_and_never_elevates_standard_user(self):
        self.assertEqual(plugin.profile_hierarchy("Administrador Principal")["tier"], 4)
        self.assertEqual(plugin.profile_hierarchy("Master")["tier"], 3)
        self.assertEqual(plugin.profile_hierarchy("Administrador")["tier"], 2)
        self.assertEqual(plugin.profile_hierarchy("Usuário")["tier"], 1)
        self.assertTrue(plugin.is_allowed_identity({"profile": "Administrador Principal", "permissions": []}))
        self.assertTrue(plugin.is_allowed_identity({"profile": "Master", "permissions": []}))
        self.assertTrue(plugin.is_allowed_identity({"profile": "Administrador", "permissions": []}))
        self.assertFalse(plugin.is_allowed_identity({"profile": "Usuário", "permissions": ["*"]}))

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

    def test_smoke_admin_is_permanently_non_identity(self):
        default = scoped_args("smoke-admin")
        self.assertFalse(plugin.command_uses_identity_governance(default))
        plugin.ensure_identity_scope_for_command(default)

        parser = plugin.build_parser()
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            parser.parse_args(["smoke-admin", "--include-identity"])

        smoke_source = inspect.getsource(plugin.cmd_smoke_admin)
        for forbidden_path in (
            "/plataforma/api/users",
            "/plataforma/api/groups",
            "/plataforma/api/email/",
            "/plataforma/api/whatsapp/",
            "/plataforma/api/codex/",
            "/plataforma/data-engine/api/",
            "/plataforma/api/rls",
        ):
            self.assertNotIn(forbidden_path, smoke_source)

    def test_parser_exposes_identity_and_operation_scope(self):
        parser = plugin.build_parser()
        users = parser.parse_args(["users", "--identity-scope", "--operation-scope", "identity"])
        self.assertTrue(users.identity_scope)
        self.assertEqual(users.operation_scope, "identity")

        smoke = parser.parse_args(["smoke-admin", "--operation-scope", "diagnostics"])
        self.assertEqual(smoke.operation_scope, "diagnostics")

    def test_every_registered_command_has_a_locked_scope(self):
        parser = plugin.build_parser()
        subcommands = next(
            action for action in parser._actions if action.__class__.__name__ == "_SubParsersAction"
        )
        unmapped = []
        for command in subcommands.choices:
            try:
                scope = plugin.operation_scope_for_command(scoped_args(command))
            except plugin.RejoinBIError:
                unmapped.append(command)
                continue
            if scope not in plugin.OPERATION_SCOPE_CHOICES:
                unmapped.append(command)
        self.assertEqual(unmapped, [])

    def test_operation_scope_is_required_and_must_match(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "locked to the 'workspace' operation scope"):
            plugin.ensure_operation_scope_for_command(scoped_args("workspaceall"))
        with self.assertRaisesRegex(plugin.RejoinBIError, "locked to the 'workspace' operation scope"):
            plugin.ensure_operation_scope_for_command(
                scoped_args("workspaceall", operation_scope="pages")
            )
        self.assertEqual(
            plugin.ensure_operation_scope_for_command(
                scoped_args("workspaceall", operation_scope="workspace")
            ),
            "workspace",
        )

    def test_raw_api_scope_is_derived_from_the_endpoint(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "locked to the 'identity' operation scope"):
            plugin.ensure_operation_scope_for_command(
                scoped_args("api-get", path="/plataforma/api/users", operation_scope="raw-api")
            )
        self.assertEqual(
            plugin.ensure_operation_scope_for_command(
                scoped_args(
                    "api-get",
                    path="/plataforma/api/users",
                    confirm_api_path="/plataforma/api/users",
                    operation_scope="identity",
                )
            ),
            "identity",
        )
        self.assertEqual(
            plugin.ensure_operation_scope_for_command(
                scoped_args(
                    "api-get",
                    path="/plataforma/api/unknown-new-endpoint",
                    confirm_api_path="/plataforma/api/unknown-new-endpoint",
                    operation_scope="raw-api",
                )
            ),
            "raw-api",
        )

    def test_raw_api_requires_exact_path_confirmation(self):
        with self.assertRaisesRegex(plugin.RejoinBIError, "--confirm-api-path"):
            plugin.ensure_operation_scope_for_command(
                scoped_args(
                    "api-get",
                    path="/plataforma/api/unknown-new-endpoint",
                    operation_scope="raw-api",
                )
            )
        with self.assertRaisesRegex(plugin.RejoinBIError, "--confirm-api-path"):
            plugin.ensure_operation_scope_for_command(
                scoped_args(
                    "api-get",
                    path="/plataforma/api/unknown-new-endpoint",
                    confirm_api_path="/plataforma/api/other-endpoint",
                    operation_scope="raw-api",
                )
            )

    def test_low_level_client_scope_lock_blocks_identity_paths(self):
        client = object.__new__(plugin.RejoinBIClient)
        client.operation_scope = "workspace"
        with self.assertRaisesRegex(plugin.RejoinBIError, "scope lock blocked"):
            client.ensure_scope_allows_path("/plataforma/api/users")

        client.operation_scope = "identity"
        client.ensure_scope_allows_path("/plataforma/api/users")

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
