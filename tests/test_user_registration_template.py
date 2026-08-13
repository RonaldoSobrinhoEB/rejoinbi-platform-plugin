from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PLUGIN_ROOT / "scripts" / "rejoinbi.py"
SPEC = importlib.util.spec_from_file_location("rejoinbi_user_template_plugin", SCRIPT)
assert SPEC and SPEC.loader
plugin = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(plugin)


class UserRegistrationTemplateTests(unittest.TestCase):
    def test_create_user_defaults_to_pin_required_and_allows_explicit_no_pin(self):
        parser = plugin.build_parser()
        required = parser.parse_args([
            "create-user",
            "--email", "user@example.com",
            "--name", "User",
        ])
        without_pin = parser.parse_args([
            "create-user",
            "--email", "user@example.com",
            "--name", "User",
            "--no-pin",
        ])
        self.assertTrue(required.pin_required)
        self.assertFalse(without_pin.pin_required)

    def test_update_user_pin_is_optional_and_does_not_change_by_default(self):
        parser = plugin.build_parser()
        unchanged = parser.parse_args(["update-user", "--user", "user@example.com"])
        disabled = parser.parse_args(["update-user", "--user", "user@example.com", "--no-pin"])
        self.assertIsNone(unchanged.pin_required)
        self.assertFalse(disabled.pin_required)

    def test_xlsx_template_has_contract_and_reads_pin_column(self):
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "usuarios.xlsx"
            plugin.write_user_template(destination)
            self.assertEqual(zipfile.ZipFile(destination).testzip(), None)

            with zipfile.ZipFile(destination, "r") as source:
                entries = {name: source.read(name) for name in source.namelist()}
            entries["xl/worksheets/sheet1.xml"] = plugin._xlsx_sheet_xml([
                list(plugin.USER_TEMPLATE_COLUMNS),
                ["user@example.com", "User", "123", "Comercial", "5511999999999", "Usuário", "não"],
            ]).encode("utf-8")
            filled = Path(temporary) / "usuarios-preenchidos.xlsx"
            with zipfile.ZipFile(filled, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for name, content in entries.items():
                    target.writestr(name, content)

            rows = plugin.read_user_xlsx_rows(filled)
            self.assertEqual(len(rows), 1)
            payload = plugin._user_payload_from_row(rows[0])
            self.assertEqual(payload["email"], "user@example.com")
            self.assertFalse(payload["pin_required"])

    def test_pin_values_are_strict_and_default_is_required(self):
        self.assertTrue(plugin._parse_user_pin_required("obrigatório"))
        self.assertFalse(plugin._parse_user_pin_required("sem pin"))
        self.assertTrue(plugin._parse_user_pin_required(""))
        with self.assertRaises(plugin.RejoinBIError):
            plugin._parse_user_pin_required("talvez")


if __name__ == "__main__":
    unittest.main()
