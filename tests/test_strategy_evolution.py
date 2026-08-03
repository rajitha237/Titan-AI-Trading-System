"""Strategy evolution safety tests."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.learning.strategy_evolution_engine import (
    build_strategy_evolution_snapshot,
)


class StrategyEvolutionTests(unittest.TestCase):
    def test_small_sample_never_changes_weight(self):
        experiences = [
            {
                "strategy": "TREND",
                "market_regime": "BULLISH",
                "session": "LONDON",
                "outcome": "WIN",
                "net_pnl": 1.0,
            }
            for _ in range(3)
        ]

        with patch(
            "app.learning.strategy_evolution_engine.list_experiences",
            return_value=experiences,
        ):
            snapshot = build_strategy_evolution_snapshot()

        item = snapshot["entries"][0]
        self.assertEqual(item["status"], "INSUFFICIENT_SAMPLE")
        self.assertEqual(item["weight"], 1.0)


if __name__ == "__main__":
    unittest.main()
