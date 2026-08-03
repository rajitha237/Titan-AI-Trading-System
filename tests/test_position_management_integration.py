from __future__ import annotations

import unittest

from app.risk.dynamic_position_sizer import (
    calculate_dynamic_position_size,
)
from app.risk.portfolio_exposure_manager import (
    evaluate_portfolio_exposure,
)


class PositionManagementIntegrationTests(
    unittest.TestCase
):
    def test_sized_trade_passes_empty_portfolio(self):
        sizing = calculate_dynamic_position_size(
            balance=30.0,
            confidence_score=85.0,
            volatility_percent=1.0,
            minimum_position_usdt=5.0,
        )

        exposure = evaluate_portfolio_exposure(
            balance=30.0,
            proposed_symbol="SOLUSDT",
            proposed_side="BUY",
            proposed_position_usdt=sizing[
                "recommended_position_usdt"
            ],
            open_positions=[],
        )

        self.assertTrue(sizing["executable"])
        self.assertTrue(exposure["allowed"])


if __name__ == "__main__":
    unittest.main()
