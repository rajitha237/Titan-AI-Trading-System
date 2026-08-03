from __future__ import annotations
import unittest
from app.performance.drawdown_analyzer import analyze_drawdown


class DrawdownAnalyzerTests(unittest.TestCase):
    def test_maximum_drawdown(self):
        result = analyze_drawdown([
            {"index": 0, "equity": 30.0},
            {"index": 1, "equity": 35.0},
            {"index": 2, "equity": 28.0},
        ])
        self.assertEqual(
            result["maximum_drawdown"],
            7.0,
        )
        self.assertGreater(
            result["maximum_drawdown_percent"],
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
