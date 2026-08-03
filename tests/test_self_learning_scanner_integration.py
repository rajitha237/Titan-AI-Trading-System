from __future__ import annotations
import unittest
from app.learning.confidence_calibration_engine import calibrate_learning_confidence

class SelfLearningScannerIntegrationTests(unittest.TestCase):
    def test_learning_is_advisory_only(self):
        evidence = {"adjustment": 5.0}
        result = calibrate_learning_confidence(
            base_score=70,
            symbol_evidence=evidence,
            strategy_evidence=evidence,
            regime_evidence=evidence,
            session_evidence=evidence,
            pattern_memory={"confidence_adjustment": 6.0},
        )
        self.assertTrue(result["advisory_only"])
        self.assertEqual(result["maximum_total_adjustment"], 5.0)

    def test_zero_sample_evidence_stays_neutral(self):
        neutral = {"adjustment": 0.0}
        result = calibrate_learning_confidence(
            base_score=75,
            symbol_evidence=neutral,
            strategy_evidence=neutral,
            regime_evidence=neutral,
            session_evidence=neutral,
            pattern_memory={"confidence_adjustment": 0.0},
        )
        self.assertEqual(result["learning_adjustment"], 0.0)
        self.assertEqual(result["calibrated_score"], 75.0)

if __name__ == "__main__":
    unittest.main()
