import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "rejoinbi"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "rejoinbi.py"
SPEC = importlib.util.spec_from_file_location("rejoinbi_delivery_cli", SCRIPT_PATH)
rejoinbi = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(rejoinbi)


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append({"method": method, "path": path, **kwargs})
        return {"success": True}, None


def delivery_args(action, **overrides):
    values = {
        "action": action,
        "data_file": None,
        "data_json": None,
        "group_id": None,
        "page_id": None,
        "limit": None,
        "session_id": None,
        "recipient_id": None,
        "contact_id": None,
        "schedule_id": 7,
        "history_id": None,
        "schedule_file": None,
        "refresh_id": None,
        "yes": True,
        "json": True,
        "timeout": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class DeliveryScheduleBridgeTests(unittest.TestCase):
    def test_email_group_attaches_project_schedule_manifest(self):
        client = FakeClient()
        manifest = {
            "id": "producao-geral-08h",
            "page_id": "producao-geral",
            "time": "08:00",
            "trigger": "after_update",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "rejoinbi-schedule.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            args = delivery_args("create-group", schedule_file=str(manifest_path))
            with (
                patch.object(rejoinbi, "make_client", return_value=client),
                patch.object(rejoinbi, "print_payload"),
            ):
                self.assertEqual(rejoinbi.cmd_email_manager(args), 0)

        self.assertEqual(client.calls[0]["method"], "POST")
        self.assertEqual(client.calls[0]["path"], "/plataforma/api/email/groups/create")
        self.assertEqual(client.calls[0]["json"]["schedule_manifest"], manifest)

    def test_whatsapp_schedule_manifests_are_scoped_to_page(self):
        client = FakeClient()
        args = delivery_args("schedule-manifests", page_id="producao-geral")
        with (
            patch.object(rejoinbi, "make_client", return_value=client),
            patch.object(rejoinbi, "print_payload"),
        ):
            self.assertEqual(rejoinbi.cmd_whatsapp_manager(args), 0)

        self.assertEqual(client.calls[0]["method"], "GET")
        self.assertEqual(
            client.calls[0]["path"],
            "/plataforma/api/whatsapp/schedule-manifests?page_id=producao-geral",
        )

    def test_refresh_complete_sends_page_and_refresh_identity(self):
        client = FakeClient()
        args = delivery_args(
            "refresh-complete",
            page_id="producao-geral",
            refresh_id="producao-geral-2026-08-09-08h",
        )
        with (
            patch.object(rejoinbi, "make_client", return_value=client),
            patch.object(rejoinbi, "print_payload"),
        ):
            self.assertEqual(rejoinbi.cmd_email_manager(args), 0)

        self.assertEqual(
            client.calls[0]["path"],
            "/plataforma/api/email/project-refresh/complete",
        )
        self.assertEqual(
            client.calls[0]["json"],
            {"page_id": "producao-geral", "refresh_id": "producao-geral-2026-08-09-08h"},
        )

    def test_pause_schedule_defaults_to_paused_payload(self):
        client = FakeClient()
        args = delivery_args("pause-schedule", schedule_id=11)
        with (
            patch.object(rejoinbi, "make_client", return_value=client),
            patch.object(rejoinbi, "print_payload"),
        ):
            self.assertEqual(rejoinbi.cmd_whatsapp_manager(args), 0)

        self.assertEqual(
            client.calls[0]["path"],
            "/plataforma/api/whatsapp/schedules/11/status",
        )
        self.assertEqual(client.calls[0]["json"], {"is_paused": True})


if __name__ == "__main__":
    unittest.main()
