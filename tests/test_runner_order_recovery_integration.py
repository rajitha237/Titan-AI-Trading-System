"""Runner integration tests for Order Recovery v28."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.trader.auto_testnet_runner import (
    _run_auto_testnet_cycle_unlocked,
)


class RunnerOrderRecoveryIntegrationTests(
    unittest.TestCase
):
    def test_order_query_failure_blocks_execution(self):
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
                return_value=(
                    [],
                    "order network error",
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
            result["mode"],
            "ORDER_RECOVERY_LOCK",
        )
        self.assertFalse(
            result["execution"]["submitted"]
        )

    def test_verified_empty_orders_run_recovery(self):
        recovery = {
            "status": "success",
            "version": "v28",
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
                return_value=recovery,
            ) as recovery_mock,
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

        recovery_mock.assert_called_once_with(
            exchange_orders=[],
            open_positions=[],
        )
        self.assertEqual(
            result["order_recovery"][
                "status"
            ],
            "success",
        )


if __name__ == "__main__":
    unittest.main()
