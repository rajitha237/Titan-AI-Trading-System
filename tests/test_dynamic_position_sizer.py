from __future__ import annotations

import unittest

from app.risk.dynamic_position_sizer import (
    calculate_dynamic_position_size,
)


class DynamicPositionSizerTests(unittest.TestCase):
    def test_position_is_capped_at_25_percent(self):
        result = calculate_dynamic_position_size(
            balance=30.0,
            base_risk_percent=1.0,
            stop_loss_percent=1.0,
            confidence_score=90.0,
            volatility_percent=1.0,
        )

        self.assertLessEqual(
            result["recommended_position_usdt"],
            7.5,
        )

    def test_high_volatility_reduces_risk(self):
        low = calculate_dynamic_position_size(
            balance=100.0,
            volatility_percent=1.0,
        )
        high = calculate_dynamic_position_size(
            balance=100.0,
            volatility_percent=4.0,
        )

        self.assertLess(
            high["effective_risk_percent"],
            low["effective_risk_percent"],
        )


if __name__ == "__main__":
    unittest.main()
