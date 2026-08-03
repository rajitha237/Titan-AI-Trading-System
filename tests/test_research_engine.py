"""Offline tests for Research Engine v2."""

from __future__ import annotations

import unittest

from app.research.dataset_split import chronological_split
from app.research.feature_engine import generate_features
from app.research.market_regime_detector import detect_market_regime
from app.research.pattern_similarity import find_similar_patterns
from app.research.sk_system_engine import calculate_sk_features
from app.research.strategy import StrategyParameters, build_strategy_signals

from tests.helpers import make_candles


class ResearchEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candles = make_candles()
        features = generate_features(candles)
        features = detect_market_regime(features)
        cls.features = calculate_sk_features(features)

    def test_feature_columns_exist(self):
        required = {
            "ema20",
            "ema50",
            "ema200",
            "rsi14",
            "adx14",
            "macd_hist",
            "atr14",
            "vwap",
            "trend_regime",
            "market_regime",
            "sk_buy_confirmed",
            "sk_sell_confirmed",
        }
        self.assertTrue(required.issubset(self.features.columns))

    def test_chronological_split_has_no_overlap(self):
        split = chronological_split(self.features)
        self.assertGreater(len(split["train"]), 0)
        self.assertGreater(len(split["validation"]), 0)
        self.assertGreater(len(split["test"]), 0)

        train_last = split["train"]["open_time"].iloc[-1]
        validation_first = split["validation"]["open_time"].iloc[0]
        validation_last = split["validation"]["open_time"].iloc[-1]
        test_first = split["test"]["open_time"].iloc[0]

        self.assertLess(train_last, validation_first)
        self.assertLess(validation_last, test_first)

    def test_strategy_generates_valid_values(self):
        signals = build_strategy_signals(
            self.features,
            parameters=StrategyParameters(
                minimum_score=70,
                require_sk=False,
                require_bos=False,
                allowed_sessions=(
                    "ASIA",
                    "LONDON",
                    "NEW_YORK",
                    "LATE_US",
                ),
            ),
        )
        values = set(signals["research_direction"].dropna().unique())
        self.assertTrue(values.issubset({"BUY", "SELL", "HOLD"}))

    def test_pattern_similarity_does_not_crash(self):
        result = find_similar_patterns(
            self.features,
            forward_bars=12,
            top_k=25,
        )
        self.assertIn(
            result["status"],
            {
                "ready",
                "insufficient_data",
                "insufficient_clean_data",
                "no_forward_samples",
            },
        )
        if result["status"] == "ready":
            self.assertGreater(result["sample_size"], 0)
            self.assertGreaterEqual(
                result["positive_probability_percent"], 0
            )
            self.assertLessEqual(
                result["positive_probability_percent"], 100
            )


if __name__ == "__main__":
    unittest.main()
