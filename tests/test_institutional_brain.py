"""Offline tests for TitanAI Institutional Brain v1."""

from __future__ import annotations

import unittest

from app.ai.adaptive_score_engine import build_adaptive_score
from app.ai.institutional_probability_engine import (
    calculate_institutional_probabilities,
)
from app.ai.institutional_strategy_selector import (
    select_institutional_strategy,
)
from app.ai.market_regime_engine_v2 import (
    classify_live_market_regime,
)
from app.ai.research_confluence_engine import (
    evaluate_research_confluence,
)


class InstitutionalBrainTests(unittest.TestCase):
    def setUp(self):
        self.technical = {
            "trend": "BULLISH",
            "rsi": 56,
            "macd_direction": "BUY",
            "adx": 29,
            "atr_percent": 1.1,
        }
        self.multi_timeframe = {
            "overall_trend": "BULLISH",
            "trend": "BULLISH",
            "alignment_score": 80,
        }
        self.market_structure = {
            "structure": "BULLISH",
            "signal": "BULLISH_BOS",
            "bos": True,
            "choch": False,
        }
        self.vwap = {
            "bias": "ABOVE_VWAP",
            "trend": "RISING",
        }
        self.volume_profile = {
            "position": "ABOVE_VALUE",
            "signal": "BULLISH",
        }
        self.order_flow = {
            "pressure": "AGGRESSIVE_BUYERS",
            "delta_ratio": 0.25,
        }
        self.liquidity_sweep = {
            "signal": "BULLISH_SWEEP",
            "direction": "BUY",
        }
        self.fair_value_gaps = {
            "signal": "BULLISH_FVG_NEARBY",
            "direction": "BUY",
        }

    def test_institutional_pipeline_shapes(self):
        regime = classify_live_market_regime(
            technical=self.technical,
            multi_timeframe=self.multi_timeframe,
            market_structure=self.market_structure,
            vwap=self.vwap,
            volume_profile=self.volume_profile,
            order_flow=self.order_flow,
            liquidity_sweep=self.liquidity_sweep,
        )
        self.assertIsInstance(regime, dict)
        self.assertIn("regime", regime)

        strategy = select_institutional_strategy(
            regime=regime,
            market_structure=self.market_structure,
            fair_value_gaps=self.fair_value_gaps,
            liquidity_sweep=self.liquidity_sweep,
            vwap=self.vwap,
            order_flow=self.order_flow,
        )
        self.assertIsInstance(strategy, dict)
        self.assertIn("selected_strategy", strategy)

        research = evaluate_research_confluence(
            {
                "status": "ready",
                "decision": "SUPPORT",
                "confidence_adjustment": 4,
                "sample_size": 50,
                "approved": True,
            }
        )
        self.assertIsInstance(research, dict)
        self.assertIn("decision", research)

        ai_score = {
            "score": 88,
            "raw_score": 88,
            "signal": "BUY",
        }
        probabilities = calculate_institutional_probabilities(
            ai_score=ai_score,
            regime=regime,
            strategy=strategy,
            research=research,
        )
        self.assertIsInstance(probabilities, dict)
        self.assertIn("long_probability", probabilities)
        self.assertIn("short_probability", probabilities)
        self.assertIn("no_trade_probability", probabilities)

        total = (
            float(probabilities["long_probability"])
            + float(probabilities["short_probability"])
            + float(probabilities["no_trade_probability"])
        )
        self.assertAlmostEqual(total, 100.0, places=1)

        adaptive = build_adaptive_score(
            ai_score=ai_score,
            regime=regime,
            strategy=strategy,
            research=research,
            probabilities=probabilities,
        )
        self.assertIsInstance(adaptive, dict)
        self.assertIn("final_score", adaptive)
        self.assertIn("action", adaptive)
        self.assertGreaterEqual(float(adaptive["final_score"]), 0)
        self.assertLessEqual(float(adaptive["final_score"]), 100)


if __name__ == "__main__":
    unittest.main()
