"""Pattern Memory safety-bound regression tests."""

from __future__ import annotations

import unittest

from app.ai.adaptive_score_engine import (
    build_adaptive_score,
)


def score(
    pattern_memory: dict,
    *,
    hard_block: bool = False,
) -> dict:
    return build_adaptive_score(
        ai_score={
            "score": 88,
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
            "hard_block": hard_block,
        },
        probabilities={
            "long_probability": 84,
            "short_probability": 8,
            "institutional_threshold_passed":
                True,
        },
        pattern_memory=pattern_memory,
    )


class PatternAdjustmentSafetyTests(
    unittest.TestCase
):
    def test_small_sample_has_zero_adjustment(self):
        result = score(
            {
                "sample_size": 4,
                "confidence_adjustment": 6,
            }
        )

        self.assertEqual(
            result["pattern_adjustment"],
            0.0,
        )

    def test_positive_adjustment_is_capped(self):
        result = score(
            {
                "sample_size": 20,
                "confidence_adjustment": 100,
            }
        )

        self.assertEqual(
            result["pattern_adjustment"],
            6.0,
        )

    def test_negative_adjustment_is_capped(self):
        result = score(
            {
                "sample_size": 20,
                "confidence_adjustment": -100,
            }
        )

        self.assertEqual(
            result["pattern_adjustment"],
            -6.0,
        )

    def test_pattern_memory_cannot_remove_hard_block(self):
        result = score(
            {
                "sample_size": 100,
                "confidence_adjustment": 6,
            },
            hard_block=True,
        )

        self.assertFalse(
            result["allowed"]
        )
        self.assertEqual(
            result["action"],
            "REJECT",
        )
        self.assertTrue(
            result["block_reasons"]
        )


if __name__ == "__main__":
    unittest.main()
