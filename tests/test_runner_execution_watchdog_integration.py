from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.trader.auto_testnet_runner import (
    _run_auto_testnet_cycle_unlocked,
)


class RunnerExecutionWatchdogIntegrationTests(
    unittest.TestCase
):
    def test_watchdog_block_prevents_scan(self):
        with (
            patch(
                "app.trader.auto_testnet_runner."
                "_get_open_position_data",
                return_value=([], None, 0),
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "synchronise_live_positions",
                return_value={
                    "status": "success",
                    "position_lifecycle": {
                        "status": "success",
                    },
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "_get_open_order_data",
                return_value=([], None),
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "recover_open_orders",
                return_value={
                    "status": "success",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "evaluate_execution_watchdog",
                return_value={
                    "status": "blocked",
                    "allowed": False,
                    "block_reasons": [
                        "test watchdog block"
                    ],
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "scan_portfolio",
            ) as scan_mock,
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

        scan_mock.assert_not_called()
        self.assertEqual(
            result["mode"],
            "EXECUTION_WATCHDOG_LOCK",
        )
        self.assertFalse(
            result["execution"]["submitted"]
        )


if __name__ == "__main__":
    unittest.main()
