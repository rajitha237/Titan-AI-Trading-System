"""Probability and confidence-bound tests."""

from __future__ import annotations

import unittest

from app.research.probability_engine import (
    estimate_trade_probability,
    wilson_lower_bound,
)


class ProbabilityEngineTests(unittest.TestCase):
    def test_wilson_bound_is_conservative(self):
        lower = wilson_lower_bound(1, 1)
        self.assertGreater(lower, 0)
        self.assertLess(lower, 1)

    def test_probability_schema(self):
        result = estimate_trade_probability(
            {
                "trade_count": 20,
                "wins": 12,
            }
        )
        self.assertEqual(result["sample_size"], 20)
        self.assertEqual(result["raw_win_rate_percent"], 60)
        self.assertLess(
            result["confidence_lower_bound_percent"],
            result["raw_win_rate_percent"],
        )


if __name__ == "__main__":
    unittest.main()
