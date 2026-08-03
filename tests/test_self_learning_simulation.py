"""Deterministic Self-Learning v2 simulation tests.

These tests use a temporary SQLite database and never modify TitanAI's
production experience database.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.learning import experience_store
from app.learning.confidence_calibration_engine import (
    calibrate_learning_confidence,
)
from app.learning.regime_performance_engine import (
    evaluate_market_regime_performance,
)
from app.learning.session_performance_engine import (
    evaluate_session_performance,
)
from app.learning.strategy_performance_engine import (
    evaluate_strategy_performance,
)
from app.learning.symbol_performance_engine import (
    evaluate_symbol_performance,
)


def make_experience(
    *,
    index: int,
    pnl: float,
    symbol: str = "SOLUSDT",
    strategy: str = "TREND_CONTINUATION",
    market_regime: str = "BULLISH_EXPANSION",
    session: str = "LONDON",
) -> dict:
    return {
        "experience_id": f"exp-{index}",
        "trade_id": f"trade-{index}",
        "symbol": symbol,
        "side": "BUY",
        "outcome": (
            "WIN"
            if pnl > 0
            else "LOSS"
            if pnl < 0
            else "BREAKEVEN"
        ),
        "net_pnl": pnl,
        "strategy": strategy,
        "market_regime": market_regime,
        "session": session,
        "entry_price": 100.0,
        "exit_price": 101.0 if pnl > 0 else 99.0,
        "duration_seconds": 1800,
        "ai_score": 82.0,
        "confirmation_score": 90.0,
        "pattern_fingerprint": {
            "symbol": symbol,
            "side": "BUY",
            "strategy": strategy,
            "market_regime": market_regime,
            "session": session,
        },
        "context": {},
    }


class SelfLearningSimulationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "experience.db"
        self.db_patch = patch.object(
            experience_store,
            "DB_PATH",
            self.db_path,
        )
        self.db_patch.start()

    def tearDown(self):
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def _save_many(self, pnls: list[float]) -> None:
        for index, pnl in enumerate(pnls, start=1):
            experience_store.save_experience(
                make_experience(
                    index=index,
                    pnl=pnl,
                )
            )

    def test_ten_positive_experiences_create_bounded_support(self):
        self._save_many([1.0] * 8 + [-0.5] * 2)

        symbol = evaluate_symbol_performance("SOLUSDT")
        strategy = evaluate_strategy_performance(
            "TREND_CONTINUATION"
        )
        regime = evaluate_market_regime_performance(
            "BULLISH_EXPANSION"
        )
        session = evaluate_session_performance("LONDON")

        for evidence in (
            symbol,
            strategy,
            regime,
            session,
        ):
            self.assertEqual(evidence["sample_size"], 10)
            self.assertGreater(evidence["adjustment"], 0.0)
            self.assertLessEqual(evidence["adjustment"], 1.0)

        calibrated = calibrate_learning_confidence(
            base_score=80.0,
            symbol_evidence=symbol,
            strategy_evidence=strategy,
            regime_evidence=regime,
            session_evidence=session,
            pattern_memory={
                "sample_size": 10,
                "confidence_adjustment": 4.0,
            },
        )

        self.assertGreater(
            calibrated["calibrated_score"],
            80.0,
        )
        self.assertLessEqual(
            calibrated["learning_adjustment"],
            5.0,
        )

    def test_ten_negative_experiences_create_bounded_opposition(self):
        self._save_many([-1.0] * 8 + [0.25] * 2)

        symbol = evaluate_symbol_performance("SOLUSDT")
        strategy = evaluate_strategy_performance(
            "TREND_CONTINUATION"
        )
        regime = evaluate_market_regime_performance(
            "BULLISH_EXPANSION"
        )
        session = evaluate_session_performance("LONDON")

        for evidence in (
            symbol,
            strategy,
            regime,
            session,
        ):
            self.assertEqual(evidence["sample_size"], 10)
            self.assertLess(evidence["adjustment"], 0.0)
            self.assertGreaterEqual(evidence["adjustment"], -1.0)

        calibrated = calibrate_learning_confidence(
            base_score=80.0,
            symbol_evidence=symbol,
            strategy_evidence=strategy,
            regime_evidence=regime,
            session_evidence=session,
            pattern_memory={
                "sample_size": 10,
                "confidence_adjustment": -4.0,
            },
        )

        self.assertLess(
            calibrated["calibrated_score"],
            80.0,
        )
        self.assertGreaterEqual(
            calibrated["learning_adjustment"],
            -5.0,
        )

    def test_nine_experiences_have_zero_influence(self):
        self._save_many([1.0] * 9)

        symbol = evaluate_symbol_performance("SOLUSDT")

        self.assertEqual(symbol["sample_size"], 9)
        self.assertEqual(symbol["adjustment"], 0.0)
        self.assertEqual(
            symbol["decision"],
            "INSUFFICIENT_SAMPLE",
        )

    def test_production_database_is_not_used(self):
        self._save_many([1.0] * 10)

        self.assertTrue(self.db_path.exists())
        self.assertEqual(
            experience_store.count_experiences(),
            10,
        )


if __name__ == "__main__":
    unittest.main()
