"""Tests for live Pattern Memory integration."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.ai.adaptive_score_engine import (
    build_adaptive_score,
)
from app.learning.live_fingerprint_builder import (
    build_live_pattern_fingerprint,
)


class LivePatternIntegrationTests(
    unittest.TestCase
):
    def test_live_fingerprint_matches_experience_schema(self):
        fingerprint = build_live_pattern_fingerprint(
            symbol="SOLUSDT",
            side="BUY",
            technical={
                "trend": "BULLISH",
                "macd_direction": "BUY",
                "rsi": 57,
                "adx": 31,
            },
            order_flow={
                "pressure": "AGGRESSIVE_BUYERS",
                "delta_ratio": 0.28,
            },
            order_book={
                "pressure": "BUY_PRESSURE",
            },
            live_regime={
                "regime": "BULLISH_EXPANSION",
            },
            institutional_strategy={
                "selected_strategy":
                    "TREND_CONTINUATION",
            },
            research_confluence={
                "decision": "SUPPORT",
            },
            now=datetime(
                2026,
                1,
                1,
                10,
                tzinfo=timezone.utc,
            ),
        )

        required = {
            "symbol",
            "side",
            "session",
            "market_regime",
            "strategy",
            "technical_trend",
            "macd_direction",
            "order_flow_pressure",
            "order_book_pressure",
            "research_decision",
            "rsi_bucket",
            "adx_bucket",
            "delta_bucket",
        }

        self.assertTrue(
            required.issubset(
                fingerprint
            )
        )
        self.assertEqual(
            fingerprint["session"],
            "LONDON",
        )

    def test_pattern_support_changes_score_but_not_blocks(self):
        base = build_adaptive_score(
            ai_score={
                "score": 90,
                "signal": "BUY",
            },
            regime={
                "confidence": 90,
                "direction": "BUY",
                "tradeable": True,
            },
            strategy={
                "strategy_score": 90,
                "direction": "BUY",
                "selected_strategy":
                    "TREND_CONTINUATION",
            },
            research={
                "score": 80,
                "hard_block": False,
            },
            probabilities={
                "long_probability": 85,
                "short_probability": 10,
                "institutional_threshold_passed":
                    True,
            },
        )

        supported = build_adaptive_score(
            ai_score={
                "score": 90,
                "signal": "BUY",
            },
            regime={
                "confidence": 90,
                "direction": "BUY",
                "tradeable": True,
            },
            strategy={
                "strategy_score": 90,
                "direction": "BUY",
                "selected_strategy":
                    "TREND_CONTINUATION",
            },
            research={
                "score": 80,
                "hard_block": False,
            },
            probabilities={
                "long_probability": 85,
                "short_probability": 10,
                "institutional_threshold_passed":
                    True,
            },
            pattern_memory={
                "decision": "SUPPORT",
                "sample_size": 12,
                "confidence_adjustment": 4.0,
            },
        )

        self.assertGreaterEqual(
            supported["final_score"],
            base["final_score"],
        )
        self.assertEqual(
            supported["pattern_adjustment"],
            4.0,
        )
