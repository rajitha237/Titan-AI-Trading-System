from __future__ import annotations
import unittest
from app.performance.trade_statistics import calculate_trade_statistics


class TradeStatisticsTests(unittest.TestCase):
    def test_core_statistics(self):
        result = calculate_trade_statistics([
            {"net_pnl": 5.0},
            {"net_pnl": -2.0},
            {"net_pnl": 0.0},
        ])
        self.assertEqual(result["trade_count"], 3)
        self.assertEqual(result["wins"], 1)
        self.assertEqual(result["losses"], 1)
        self.assertEqual(result["breakeven"], 1)
        self.assertEqual(result["net_pnl"], 3.0)


if __name__ == "__main__":
    unittest.main()
