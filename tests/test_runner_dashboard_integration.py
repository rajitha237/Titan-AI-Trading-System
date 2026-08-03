from __future__ import annotations
import asyncio
import unittest
from unittest.mock import patch
from app.trader.auto_testnet_runner import (
    _run_auto_testnet_cycle_unlocked,
    run_auto_testnet_cycle,
)


class RunnerDashboardIntegrationTests(unittest.TestCase):
    def test_blocked_result_contains_dashboard(self):
        with (
            patch("app.trader.auto_testnet_runner.begin_service_cycle", return_value={
                "cycle_id": "dashboard-cycle", "mode": "ANALYSIS_ONLY", "started_at": "now"
            }),
            patch("app.trader.auto_testnet_runner.complete_service_cycle", return_value={
                "status": "blocked", "cycle_id": "dashboard-cycle"
            }),
            patch("app.trader.auto_testnet_runner._get_open_position_data",
                  return_value=([], "network unavailable", 0)),
            patch("app.trader.auto_testnet_runner.save_cycle_result", return_value=None),
            patch("app.trader.auto_testnet_runner.save_memory_record", return_value=None),
        ):
            result = asyncio.run(_run_auto_testnet_cycle_unlocked(
                execute_trade=False, scan_limit=1
            ))
        self.assertIn("dashboard", result)
        self.assertTrue(result["dashboard"]["read_only"])

    def test_concurrency_guard_has_no_scope_error(self):
        class FakeBusyLock:
            def acquire(
                self,
                blocking: bool = True,
            ) -> bool:
                return False

            def release(self) -> None:
                return None

        with (
            patch(
                "app.trader.auto_testnet_runner._CYCLE_LOCK",
                new=FakeBusyLock(),
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "begin_service_cycle",
                return_value={
                    "cycle_id": "concurrency",
                    "mode": "CONCURRENCY_GUARD",
                    "started_at": "now",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "complete_service_cycle",
                return_value={
                    "status": "skipped",
                    "cycle_id": "concurrency",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_cycle_result",
                return_value=None,
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_memory_record",
                return_value=None,
            ),
        ):
            result = asyncio.run(
                run_auto_testnet_cycle()
            )

        self.assertEqual(
            result["execution"]["mode"],
            "CONCURRENCY_GUARD",
        )
        self.assertIn(
            "dashboard",
            result,
        )


if __name__ == "__main__":
    unittest.main()
