from __future__ import annotations
import unittest
from app.trader.trade_integrity_report import build_trade_integrity_report


class TradeIntegrityReportTests(unittest.TestCase):
    def test_healthy_empty_report(self):
        result = build_trade_integrity_report(
            exchange_positions=[],
            exchange_orders=[],
            execution={"submitted": False},
            completed_trades=[],
            local_open_states=[],
        )
        self.assertEqual(result["integrity_score_percent"], 100.0)
        self.assertTrue(result["advisory_only"])


if __name__ == "__main__":
    unittest.main()
