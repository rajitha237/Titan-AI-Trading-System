from __future__ import annotations
import unittest
from app.performance.equity_curve import build_equity_curve


class EquityCurveTests(unittest.TestCase):
    def test_equity_curve_accumulates(self):
        result = build_equity_curve(
            [
                {"net_pnl": 5.0},
                {"net_pnl": -2.0},
            ],
            starting_equity=30.0,
        )
        self.assertEqual(
            result["ending_equity"],
            33.0,
        )
        self.assertEqual(
            len(result["points"]),
            3,
        )


if __name__ == "__main__":
    unittest.main()
