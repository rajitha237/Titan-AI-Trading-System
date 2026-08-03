from __future__ import annotations
import asyncio
import unittest
from unittest.mock import patch
from app.trader.auto_testnet_runner import _run_auto_testnet_cycle_unlocked


class RunnerStartupConfigurationTests(unittest.TestCase):
    def test_blocked_startup_never_queries_exchange(self):
        with (
            patch(
                "app.trader.auto_testnet_runner.evaluate_startup_readiness",
                return_value={
                    "status": "blocked",
                    "startup_allowed": False,
                    "errors": ["unsafe configuration"],
                },
            ),
            patch(
                "app.trader.auto_testnet_runner.begin_service_cycle",
                return_value={
                    "cycle_id": "startup-lock",
                    "mode": "TESTNET_EXECUTION",
                    "started_at": "now",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner.complete_service_cycle",
                return_value={
                    "status": "blocked",
                    "cycle_id": "startup-lock",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner._get_open_position_data"
            ) as exchange_mock,
            patch(
                "app.trader.auto_testnet_runner.save_cycle_result",
                return_value=None,
            ),
            patch(
                "app.trader.auto_testnet_runner.save_memory_record",
                return_value=None,
            ),
            patch(
                "app.trader.auto_testnet_runner.route_notifications",
                return_value={
                    "status": "success",
                    "event_count": 0,
                    "stored_count": 0,
                    "telegram_sent_count": 0,
                    "events": [],
                    "errors": [],
                    "non_blocking": True,
                },
            ),
        ):
            result = asyncio.run(
                _run_auto_testnet_cycle_unlocked(
                    execute_trade=True,
                    scan_limit=1,
                )
            )

        exchange_mock.assert_not_called()
        self.assertEqual(result["mode"], "STARTUP_CONFIGURATION_LOCK")
        self.assertFalse(result["execution"]["submitted"])


if __name__ == "__main__":
    unittest.main()
