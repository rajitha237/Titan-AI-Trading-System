from __future__ import annotations
import unittest
from app.ai.trade_quality_gate import evaluate_trade_quality


class TradeQualityCompatibilityTests(unittest.TestCase):
    def test_adjusted_confidence_precedes_legacy_confidence(self):
        result = evaluate_trade_quality(
            order_book={
                "pressure": "BUY_PRESSURE",
                "imbalance": 0.2,
            },
            order_flow={
                "pressure": "AGGRESSIVE_BUYERS",
                "delta_ratio": 0.2,
                "whale_trades": [],
            },
            confidence={
                "confidence": 40,
                "adjusted_confidence_score": 90,
                "signal": "BUY",
            },
            validation={
                "allowed": True,
                "decision": "BUY",
            },
            liquidity_trend={"signal": "BID_SUPPORT"},
            direction="BUY",
        )
        self.assertEqual(result["confidence_score"], 90.0)
        self.assertIn("thresholds", result)
        self.assertIn("primary_blockers", result)


if __name__ == "__main__":
    unittest.main()
