from __future__ import annotations
import unittest
from app.learning.learning_statistics import bounded_performance_adjustment, performance_metrics, sample_adjustment_cap

class LearningStatisticsTests(unittest.TestCase):
    def test_sample_caps(self):
        self.assertEqual(sample_adjustment_cap(9), 0.0)
        self.assertEqual(sample_adjustment_cap(10), 1.0)
        self.assertEqual(sample_adjustment_cap(20), 3.0)
        self.assertEqual(sample_adjustment_cap(50), 5.0)

    def test_small_sample_has_zero_influence(self):
        metrics = performance_metrics([{"net_pnl": 1.0} for _ in range(9)])
        self.assertEqual(bounded_performance_adjustment(metrics)["adjustment"], 0.0)

if __name__ == "__main__":
    unittest.main()
