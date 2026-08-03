from __future__ import annotations

import unittest

from app.risk.portfolio_exposure_manager import (
    evaluate_portfolio_exposure,
)


class PortfolioExposureManagerTests(unittest.TestCase):
    def test_no_open_positions_allows_bounded_trade(self):
        result = evaluate_portfolio_exposure(
            balance=30.0,
            proposed_symbol="BTCUSDT",
            proposed_side="BUY",
            proposed_position_usdt=7.5,
            open_positions=[],
        )

        self.assertTrue(result["allowed"])

    def test_existing_position_blocks_second_position(self):
        result = evaluate_portfolio_exposure(
            balance=30.0,
            proposed_symbol="ETHUSDT",
            proposed_side="BUY",
            proposed_position_usdt=7.5,
            open_positions=[
                {
                    "symbol": "BTCUSDT",
                    "positionAmt": "0.001",
                    "markPrice": "60000",
                }
            ],
        )

        self.assertFalse(result["allowed"])
        self.assertIn(
            "Maximum concurrent-position limit reached",
            result["block_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
