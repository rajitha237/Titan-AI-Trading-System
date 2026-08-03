from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from app.trader.auto_testnet_runner import (
    _run_auto_testnet_cycle_unlocked,
)


class RunnerServiceStateIntegrationTests(
    unittest.TestCase
):
    def test_blocked_cycle_attaches_service_state(self):
        with (
            patch(
                "app.trader.auto_testnet_runner."
                "begin_service_cycle",
                return_value={
                    "cycle_id": "test-cycle",
                    "mode": "ANALYSIS_ONLY",
                    "started_at": "now",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "complete_service_cycle",
                return_value={
                    "status": "blocked",
                    "cycle_id": "test-cycle",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "_get_open_position_data",
                return_value=(
                    [],
                    "network down",
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
            result["service_state"][
                "cycle_id"
            ],
            "test-cycle",
        )


if __name__ == "__main__":
    unittest.main()
