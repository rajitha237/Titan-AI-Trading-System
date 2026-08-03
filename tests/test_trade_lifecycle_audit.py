from __future__ import annotations
import unittest
from app.trader.trade_lifecycle_audit import audit_trade_lifecycle


class TradeLifecycleAuditTests(unittest.TestCase):
    def test_consistent_empty_state(self):
        result = audit_trade_lifecycle(
            exchange_positions=[],
            exchange_orders=[],
            local_open_states=[],
            completed_trades=[],
        )
        self.assertEqual(result["status"], "consistent")
        self.assertEqual(result["issue_count"], 0)

    def test_missing_local_state_is_reported(self):
        result = audit_trade_lifecycle(
            exchange_positions=[{"symbol": "BTCUSDT", "positionAmt": "0.01"}],
            exchange_orders=[],
            local_open_states=[],
            completed_trades=[],
        )
        self.assertEqual(result["status"], "review_required")


if __name__ == "__main__":
    unittest.main()
