from __future__ import annotations
import unittest
from app.performance.performance_metrics import (
    calculate_expectancy,
    calculate_profit_factor,
    calculate_sharpe_ratio,
)


class PerformanceMetricsTests(unittest.TestCase):
    def test_profit_factor(self):
        self.assertEqual(
            calculate_profit_factor(
                20.0,
                -10.0,
            ),
            2.0,
        )

    def test_expectancy(self):
        value = calculate_expectancy(
            win_rate=0.5,
            average_win=4.0,
            loss_rate=0.5,
            average_loss=-2.0,
        )
        self.assertEqual(value, 1.0)

    def test_sharpe_small_sample_is_zero(self):
        self.assertEqual(
            calculate_sharpe_ratio([1.0]),
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
