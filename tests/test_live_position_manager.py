from __future__ import annotations

import unittest
from unittest.mock import patch

from app.trader.live_position_manager import (
    manage_live_positions,
)


class LivePositionManagerTests(unittest.TestCase):
    def test_no_positions_allows_new_entry(self):
        result = manage_live_positions(
            positions=[]
        )

        self.assertTrue(
            result["new_entry_allowed"]
        )
        self.assertEqual(
            result["active_position_count"],
            0,
        )

    @patch(
        "app.trader.live_position_manager."
        "sync_cycle_state",
        return_value={"status": "success"},
    )
    @patch(
        "app.trader.live_position_manager."
        "inspect_position_protection",
        return_value={"protected": True},
    )
    @patch(
        "app.trader.live_position_manager."
        "manage_trailing_stop_for_open_positions",
        return_value=[],
    )
    @patch(
        "app.trader.live_position_manager."
        "manage_break_even_for_open_positions",
        return_value=[],
    )
    @patch(
        "app.trader.live_position_manager."
        "manage_partial_take_profit_for_open_positions",
        return_value=[],
    )
    def test_existing_position_blocks_new_entry(
        self,
        *_mocks,
    ):
        result = manage_live_positions(
            positions=[
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": "0.001",
                    "entryPrice": "60000",
                    "markPrice": "60500",
                }
            ]
        )

        self.assertFalse(
            result["new_entry_allowed"]
        )
        self.assertTrue(
            result["all_positions_protected"]
        )


if __name__ == "__main__":
    unittest.main()
