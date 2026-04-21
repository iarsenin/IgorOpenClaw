import importlib.util
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "scripts" / "api-spend-check.py"


def load_module():
    spec = importlib.util.spec_from_file_location("api_spend_check", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ApiSpendCheckTests(unittest.TestCase):
    def test_vapi_spend_respects_the_requested_time_window(self):
        module = load_module()
        start = datetime(2026, 4, 19, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc)

        fake_calls = [
            {"startedAt": "2026-04-18T23:59:59Z", "cost": 1.25},
            {"startedAt": "2026-04-19T03:15:00Z", "cost": 2.50},
            {"startedAt": "2026-04-19T19:45:00Z", "cost": 3.00},
            {"startedAt": "2026-04-20T00:00:00Z", "cost": 9.99},
        ]

        with mock.patch.object(module, "fetch", return_value=fake_calls):
            total, count = module.vapi_spend("test-key", ctx=None, start=start, end=end)

        self.assertEqual(total, 5.50)
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
