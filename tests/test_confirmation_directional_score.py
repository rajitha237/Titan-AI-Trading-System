from __future__ import annotations
import unittest
from app.ai.confirmation_engine import evaluate_trade_confirmation


class ConfirmationDirectionalScoreTests(unittest.TestCase):
    def _neutral_inputs(self):
        return dict(
            order_flow={},
            liquidity_trend={},
            liquidity_sweep={},
            absorption={},
            iceberg={},
            whale_activity={},
            market_structure={},
            volume_profile={},
            vwap={},
            fair_value_gaps={},
            technical={},
            multi_timeframe={},
        )

    def test_sell_legacy_score_is_directional(self):
        result = evaluate_trade_confirmation(
            ai_score={"signal": "SELL", "score": 10},
            **self._neutral_inputs(),
        )
        self.assertEqual(result["raw_score"], 90)
        self.assertNotIn(
            "Raw AI score is below the trade threshold",
            result["hard_blocks"],
        )

    def test_institutional_directional_score_has_priority(self):
        result = evaluate_trade_confirmation(
            ai_score={
                "signal": "SELL",
                "score": 70,
                "institutional_directional_score": 88,
            },
            **self._neutral_inputs(),
        )
        self.assertEqual(result["raw_score"], 88)


if __name__ == "__main__":
    unittest.main()
