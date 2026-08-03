"""Position Consistency Audit v27 tests."""

from __future__ import annotations

import unittest

from app.trader.position_consistency_audit import (
    build_position_consistency_audit,
)


class PositionConsistencyAuditTests(
    unittest.TestCase
):
    def test_empty_exchange_and_local_state_are_consistent(self):
        result = build_position_consistency_audit(
            exchange_positions=[],
            local_open_states=[],
        )

        self.assertEqual(
            result["status"],
            "consistent",
        )
        self.assertEqual(
            result["issue_count"],
            0,
        )

    def test_missing_exchange_position_is_reported(self):
        result = build_position_consistency_audit(
            exchange_positions=[],
            local_open_states=[
                {
                    "symbol": "ETHUSDT",
                    "side": "SELL",
                    "status": "OPEN",
                    "entry_price": 2500.0,
                    "current_quantity": 0.01,
                }
            ],
        )

        self.assertEqual(
            result[
                "missing_exchange_positions"
            ],
            [
                {
                    "symbol": "ETHUSDT",
                    "side": "SELL",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
