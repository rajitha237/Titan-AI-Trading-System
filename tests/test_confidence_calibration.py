from __future__ import annotations
import unittest
from app.learning.confidence_calibration_engine import calibrate_learning_confidence

class ConfidenceCalibrationTests(unittest.TestCase):
    def test_total_adjustment_is_capped(self):
        evidence = {"adjustment": 100.0}
        result = calibrate_learning_confidence(
            base_score=80,
            symbol_evidence=evidence,
            strategy_evidence=evidence,
            regime_evidence=evidence,
            session_evidence=evidence,
            pattern_memory={"confidence_adjustment": 100.0},
        )
        self.assertLessEqual(result["learning_adjustment"], 5.0)
        self.assertLessEqual(result["calibrated_score"], 100.0)

    def test_negative_total_is_capped(self):
        evidence = {"adjustment": -100.0}
        result = calibrate_learning_confidence(
            base_score=80,
            symbol_evidence=evidence,
            strategy_evidence=evidence,
            regime_evidence=evidence,
            session_evidence=evidence,
            pattern_memory={"confidence_adjustment": -100.0},
        )
        self.assertGreaterEqual(result["learning_adjustment"], -5.0)
        self.assertGreaterEqual(result["calibrated_score"], 0.0)

if __name__ == "__main__":
    unittest.main()
