from __future__ import annotations
import unittest
from app.performance.performance_dashboard import build_performance_dashboard


class PerformanceDashboardTests(unittest.TestCase):
    def test_dashboard_schema(self):
        result = build_performance_dashboard(
            trades=[
                {"net_pnl": 5.0},
                {"net_pnl": -2.0},
            ],
            starting_equity=30.0,
        )
        self.assertEqual(result["status"], "success")
        self.assertIn("trade_statistics", result)
        self.assertIn("equity_curve", result)
        self.assertIn("drawdown", result)
        self.assertTrue(result["advisory_only"])


if __name__ == "__main__":
    unittest.main()
