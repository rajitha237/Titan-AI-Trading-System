from __future__ import annotations
import unittest
from unittest.mock import patch
from app.trader.auto_testnet_runner import save_result


class RunnerNotificationIntegrationTests(unittest.TestCase):
    def test_save_result_attaches_notifications(self):
        result = {
            "status": "error",
            "reason": "test failure",
            "execution": {"submitted": False},
        }
        with (
            patch(
                "app.trader.auto_testnet_runner.route_notifications",
                return_value={
                    "status": "success",
                    "event_count": 1,
                    "stored_count": 1,
                    "telegram_sent_count": 0,
                    "events": [],
                    "errors": [],
                    "non_blocking": True,
                },
            ),
            patch(
                "app.trader.auto_testnet_runner.save_cycle_result",
                return_value=None,
            ),
            patch(
                "app.trader.auto_testnet_runner.save_memory_record",
                return_value=None,
            ),
        ):
            save_result(result)
        self.assertEqual(result["notifications"]["event_count"], 1)

    def test_router_error_does_not_break_save(self):
        result = {
            "status": "skipped",
            "execution": {"submitted": False},
        }
        with (
            patch(
                "app.trader.auto_testnet_runner.route_notifications",
                side_effect=RuntimeError("notification failure"),
            ),
            patch(
                "app.trader.auto_testnet_runner.save_cycle_result",
                return_value=None,
            ),
            patch(
                "app.trader.auto_testnet_runner.save_memory_record",
                return_value=None,
            ),
        ):
            save_result(result)
        self.assertEqual(result["notifications"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
