"""Runner integration test for Live Position Synchronizer v27."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.trader.auto_testnet_runner import (
    _run_auto_testnet_cycle_unlocked,
)


class RunnerPositionSyncIntegrationTests(
    unittest.TestCase
):
    def test_position_query_failure_blocks_sync_and_execution(self):
        with (
            patch(
                "app.trader.auto_testnet_runner."
                "_get_open_position_data",
                return_value=(
                    [],
                    "network unavailable",
                    0,
                ),
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_result",
                return_value=None,
            ),
        ):
            result = asyncio.run(
                _run_auto_testnet_cycle_unlocked(
                    execute_trade=False,
                    scan_limit=1,
                )
            )

        self.assertEqual(
            result["status"],
            "blocked",
        )
        self.assertEqual(
            result[
                "live_position_sync"
            ]["status"],
            "blocked",
        )
        self.assertFalse(
            result[
                "execution"
            ]["submitted"]
        )

    def test_verified_empty_snapshot_runs_synchronizer(self):
        sync_result = {
            "status": "success",
            "version": "v27",
            "position_lifecycle": {
                "status": "success",
                "closed_positions_detected": 0,
                "completed_trades": [],
                "errors": [],
            },
        }

        with (
            patch(
                "app.trader.auto_testnet_runner."
                "_get_open_position_data",
                return_value=([], None, 0),
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "synchronise_live_positions",
                return_value=sync_result,
            ) as sync_mock,
            patch(
                "app.trader.auto_testnet_runner."
                "evaluate_daily_risk",
                return_value={
                    "allowed": False,
                    "reason": "test stop",
                    "analytics": {},
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "save_result",
                return_value=None,
            ),
        ):
            result = asyncio.run(
                _run_auto_testnet_cycle_unlocked(
                    execute_trade=False,
                    scan_limit=1,
                )
            )

        sync_mock.assert_called_once_with(
            exchange_positions=[]
        )
        self.assertEqual(
            result[
                "live_position_sync"
            ]["status"],
            "success",
        )


if __name__ == "__main__":
    unittest.main()
