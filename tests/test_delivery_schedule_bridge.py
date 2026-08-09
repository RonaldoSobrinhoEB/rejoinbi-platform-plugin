import importlib.util
import unittest
from types import SimpleNamespace
from unittest.mock import patch


PLUGIN_ROOT = __import__("pathlib").Path(__file__).resolve().parents[1] / "plugins" / "rejoinbi"
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
        "yes": True,
        "json": True,
        "timeout": 30,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class DeliveryScheduleControlTests(unittest.TestCase):
    def test_email_pause_and_resume_use_status_endpoint(self):
        client = FakeClient()
        with (
            patch.object(rejoinbi, "make_client", return_value=client),
            patch.object(rejoinbi, "print_payload"),
        ):
            self.assertEqual(rejoinbi.cmd_email_manager(delivery_args("pause-schedule", schedule_id=11)), 0)
            self.assertEqual(rejoinbi.cmd_email_manager(delivery_args("resume-schedule", schedule_id=11)), 0)

        self.assertEqual(client.calls[0]["path"], "/plataforma/api/email/schedules/11/status")
        self.assertEqual(client.calls[0]["json"], {"is_paused": True})
        self.assertEqual(client.calls[1]["json"], {"is_paused": False})

    def test_whatsapp_pause_uses_status_endpoint(self):
        client = FakeClient()
        with (
            patch.object(rejoinbi, "make_client", return_value=client),
            patch.object(rejoinbi, "print_payload"),
        ):
            self.assertEqual(rejoinbi.cmd_whatsapp_manager(delivery_args("pause-schedule", schedule_id=27)), 0)

        self.assertEqual(client.calls[0]["path"], "/plataforma/api/whatsapp/schedules/27/status")
        self.assertEqual(client.calls[0]["json"], {"is_paused": True})

    def test_group_payload_is_forwarded_without_schedule_manifest(self):
        client = FakeClient()
        args = delivery_args(
            "create-group",
            data_json='{"group_name":"Relatório"}',
        )
        with (
            patch.object(rejoinbi, "make_client", return_value=client),
            patch.object(rejoinbi, "print_payload"),
        ):
            self.assertEqual(rejoinbi.cmd_email_manager(args), 0)

        self.assertEqual(client.calls[0]["json"], {"group_name": "Relatório"})
        self.assertNotIn("schedule_manifest", client.calls[0]["json"])

    def test_parser_no_longer_exposes_refresh_or_schedule_file_flow(self):
        parser = rejoinbi.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["email", "schedule-manifests"])
        with self.assertRaises(SystemExit):
            parser.parse_args(["email", "create-group", "--schedule-file", "project.json"])


if __name__ == "__main__":
    unittest.main()
