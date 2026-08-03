"""Deterministic offline test for TitanAI's pre-execution chain."""

from __future__ import annotations

import unittest

from app.ai.confirmation_engine import evaluate_trade_confirmation
from app.ai.trade_quality_gate import evaluate_trade_quality
from app.risk.risk_engine import calculate_risk_plan
from app.trader.trade_builder import build_trade_plan
from app.trader.trade_validator import validate_trade


class EndToEndAnalysisTests(unittest.TestCase):
    def test_approved_buy_setup_reaches_ready_trade_plan(self):
        ai_score = {
            "score": 96.0,
            "signal": "BUY",
        }
        final_decision = {
            "decision": "BUY",
        }
        order_book = {
            "pressure": "BUY_PRESSURE",
            "imbalance": 0.24,
        }
        order_flow = {
            "pressure": "AGGRESSIVE_BUYERS",
            "delta_ratio": 0.31,
        }
        liquidity_trend = {
            "signal": "ASK_WALL_REMOVED",
            "latest_pressure": "BID_LIQUIDITY_STRONG",
        }
        liquidity_sweep = {
            "signal": "BULLISH_SWEEP",
            "direction": "BUY",
        }
        market_structure = {
            "structure": "BULLISH",
            "signal": "BULLISH_BOS",
        }
        volume_profile = {
            "position": "ABOVE_VALUE",
            "signal": "BULLISH",
        }
        vwap = {
            "bias": "ABOVE_VWAP",
            "trend": "RISING",
        }
        fair_value_gaps = {
            "signal": "BULLISH_FVG_NEARBY",
            "direction": "BUY",
        }
        technical = {
            "trend": "BULLISH",
            "macd_direction": "BUY",
            "rsi_signal": "NEUTRAL",
        }
        multi_timeframe = {
            "overall_trend": "BULLISH",
        }
        whale_activity = {
            "state": "ACCUMULATION",
            "samples": 10,
            "reliability": "RELIABLE",
        }

        confirmation = evaluate_trade_confirmation(
            ai_score=ai_score,
            order_flow=order_flow,
            liquidity_trend=liquidity_trend,
            liquidity_sweep=liquidity_sweep,
            absorption={},
            iceberg={},
            whale_activity=whale_activity,
            market_structure=market_structure,
            volume_profile=volume_profile,
            vwap=vwap,
            fair_value_gaps=fair_value_gaps,
            technical=technical,
            multi_timeframe=multi_timeframe,
        )

        self.assertTrue(confirmation.get("passed"))
        self.assertEqual(confirmation.get("decision"), "APPROVE")

        enriched_decision = {
            **final_decision,
            "confirmation_score": confirmation.get(
                "confirmation_score",
                confirmation.get("score", 0),
            ),
            "whale_activity": "ACCUMULATION",
            "liquidity": "ASK_WALL_REMOVED",
        }
        enriched_score = {
            **ai_score,
            "confirmation_score": enriched_decision[
                "confirmation_score"
            ],
            "whale_activity": "ACCUMULATION",
            "liquidity": "ASK_WALL_REMOVED",
        }
        enriched_technical = {
            **technical,
            "market_structure": "BULLISH",
            "vwap_position": "ABOVE_VWAP",
            "fvg_signal": "BULLISH_FVG_NEARBY",
        }

        validation = validate_trade(
            final_decision=enriched_decision,
            ai_score=enriched_score,
            order_book=order_book,
            technical=enriched_technical,
            multi_timeframe=multi_timeframe,
        )

        self.assertTrue(validation.get("allowed"))

        confidence = {
            "confidence": 96.0,
            "signal": "BUY",
            "decision": "TRADE",
        }
        trade_quality = evaluate_trade_quality(
            order_book=order_book,
            order_flow=order_flow,
            confidence=confidence,
            validation=validation,
            liquidity_trend=liquidity_trend,
            direction="BUY",
        )

        self.assertTrue(trade_quality.get("passed"))
        self.assertIn(
            trade_quality.get("action"),
            {"TRADE", "SMALL_TRADE"},
        )

        risk_plan = calculate_risk_plan(
            balance=30.0,
            risk_percent=1.0,
            leverage=5.0,
            stop_loss_percent=1.0,
            take_profit_percent=1.5,
            confirmation=confirmation,
            require_confirmation=True,
            trade_quality_action=trade_quality.get("action"),
            current_daily_pnl=0.0,
            open_positions_count=0,
            minimum_risk_reward=1.0,
            maximum_risk_percent=2.0,
            maximum_leverage=5.0,
            maximum_position_percent=25.0,
            maximum_daily_loss_percent=3.0,
            maximum_concurrent_positions=1,
            mode="ANALYSIS",
        )

        self.assertTrue(risk_plan.get("approved"))
        self.assertTrue(risk_plan.get("approved"))
        self.assertFalse(risk_plan.get("execution_allowed"))
        self.assertEqual(
             risk_plan.get("execution_mode"),
             "RISK_ANALYSIS_ONLY",
        )

        trade_plan = build_trade_plan(
            symbol="ADAUSDT",
            price=0.50,
            final_decision=final_decision,
            confirmation=confirmation,
            risk_plan=risk_plan,
            quantity=15.0,
            exchange_filters={
                "min_notional": 5.0,
                "min_qty": 1.0,
                "step_size": 1.0,
                "tick_size": 0.0001,
            },
        )

        self.assertTrue(trade_plan.get("ready"))
        self.assertTrue(trade_plan.get("execution_allowed"))
        self.assertGreater(float(trade_plan.get("quantity", 0)), 0)
        self.assertGreater(
            float(trade_plan.get("actual_order_notional", 0)),
            0,
        )
        self.assertEqual(trade_plan.get("side"), "BUY")


if __name__ == "__main__":
    unittest.main()
