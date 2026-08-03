from __future__ import annotations
import unittest
from app.trader.restart_integrity_checker import check_restart_integrity


class RestartIntegrityTests(unittest.TestCase):
    def test_matching_state_is_ready(self):
        result = check_restart_integrity(
            exchange_positions=[
                {"symbol": "BTCUSDT", "positionAmt": "0.01"}
            ],
            exchange_orders=[],
            local_open_states=[
                {
                    "symbol": "BTCUSDT",
                    "side": "BUY",
                    "protection_verified": True,
                }
            ],
            completed_trades=[],
        )
        self.assertTrue(result["restart_safe"])

    def test_missing_exchange_position_blocks(self):
        result = check_restart_integrity(
            exchange_positions=[],
            exchange_orders=[],
            local_open_states=[
                {"symbol": "BTCUSDT", "side": "BUY"}
            ],
            completed_trades=[],
        )
        self.assertFalse(result["restart_safe"])


if __name__ == "__main__":
    unittest.main()
