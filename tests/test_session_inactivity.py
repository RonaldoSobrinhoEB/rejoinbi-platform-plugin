import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch


PLUGIN_ROOT = Path(__file__).resolve().parents[1] / "plugins" / "rejoinbi"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "rejoinbi.py"
SPEC = importlib.util.spec_from_file_location("rejoinbi_session_cli", SCRIPT_PATH)
rejoinbi = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(rejoinbi)


class SessionInactivityTests(unittest.TestCase):
    base_url = "https://tenant.rejoinbi.com.br"

    def _session_payload(self, hours_ago):
        last_used = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {
            "base_url": self.base_url,
            "cookies": {"plataforma_session": "signed-cookie"},
            "saved_at": last_used.isoformat(),
            "last_used_at": last_used.isoformat(),
            "last_used_ts": last_used.timestamp(),
        }

    def test_session_is_kept_before_24_hours_of_inactivity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session_path = session_dir / f"{rejoinbi.session_slug(self.base_url)}.json"
            rejoinbi.write_json(session_path, self._session_payload(23))

            with patch.object(rejoinbi, "SESSION_DIR", session_dir):
                client = rejoinbi.RejoinBIClient(self.base_url)

            self.assertTrue(session_path.exists())
            self.assertEqual(client.session.cookies.get("plataforma_session"), "signed-cookie")

    def test_session_is_discarded_after_24_hours_of_inactivity(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session_path = session_dir / f"{rejoinbi.session_slug(self.base_url)}.json"
            rejoinbi.write_json(session_path, self._session_payload(25))

            with patch.object(rejoinbi, "SESSION_DIR", session_dir):
                client = rejoinbi.RejoinBIClient(self.base_url)

            self.assertFalse(session_path.exists())
            self.assertIsNone(client.session.cookies.get("plataforma_session"))

    def test_authenticated_use_renews_last_used_timestamp(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            session_dir = Path(temp_dir)
            session_path = session_dir / f"{rejoinbi.session_slug(self.base_url)}.json"
            payload = self._session_payload(1)
            rejoinbi.write_json(session_path, payload)

            with patch.object(rejoinbi, "SESSION_DIR", session_dir):
                client = rejoinbi.RejoinBIClient(self.base_url)
                client._last_session_touch_ts = payload["last_used_ts"]
                client.touch_session_usage(force=True)

            refreshed = rejoinbi.read_json(session_path, {})
            self.assertGreater(refreshed["last_used_ts"], payload["last_used_ts"])
            self.assertEqual(
                refreshed["idle_timeout_seconds"],
                rejoinbi.SESSION_IDLE_TIMEOUT_SECONDS,
            )


if __name__ == "__main__":
    unittest.main()
