"""Dynamic Risk v26.1 runner integration tests."""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from app.trader.auto_testnet_runner import (
    _evaluate_candidate_for_selection,
)


def sample_candidate() -> dict:
    return {
        "symbol": "SOLUSDT",
        "price": 100.0,
        "ai_score": {
            "signal": "BUY",
            "score": 90.0,
        },
        "final_decision": {
            "decision": "BUY",
        },
        "validation": {
            "allowed": True,
        },
        "order_book": {},
        "order_flow": {},
        "technical": {
            "atr_percent": 2.0,
        },
        "multi_timeframe": {},
    }


class RunnerDynamicRiskIntegrationTests(
    unittest.TestCase
):
    def test_dynamic_diagnostics_are_exposed(self):
        with (
            patch(
                "app.trader.auto_testnet_runner."
                "calculate_confidence",
                return_value={
                    "decision": "TRADE",
                    "adjusted_confidence_score": 90.0,
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "evaluate_trade_confirmation",
                return_value={
                    "passed": True,
                    "approved": True,
                    "decision": "APPROVE",
                    "confirmation_score": 90.0,
                    "hard_blocks": [],
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "validate_trade",
                return_value={
                    "allowed": True,
                    "reason": "approved",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "evaluate_trade_quality",
                return_value={
                    "passed": True,
                    "action": "TRADE",
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "calculate_risk_plan",
                return_value={
                    "approved": True,
                    "execution_allowed": True,
                    "position_size_usdt": 7.5,
                    "margin_required": 1.5,
                    "stop_loss_percent": 1.0,
                    "take_profit_percent": 2.0,
                    "risk_reward_ratio": 2.0,
                    "leverage": 5.0,
                    "risk_amount": 0.3,
                    "block_reasons": [],
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "build_trade_plan",
                return_value={
                    "ready": True,
                    "execution_allowed": True,
                    "quantity": 0.075,
                    "position_size_usdt": 7.5,
                    "margin_required": 1.5,
                    "block_reasons": [],
                },
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "get_symbol_filters",
                new=AsyncMock(
                    return_value={
                        "min_notional": 5.0,
                        "min_qty": 0.001,
                        "step_size": 0.001,
                    }
                ),
            ),
            patch(
                "app.trader.auto_testnet_runner."
                "evaluate_account_protection",
                return_value={
                    "allowed": True,
                },
            ),
        ):
            result = asyncio.run(
                _evaluate_candidate_for_selection(
                    sample_candidate(),
                    quantity=None,
                    balance=30.0,
                    risk_percent=1.0,
                    leverage=5.0,
                    current_daily_pnl=0.0,
                    open_positions_count=0,
                    open_positions=[],
                )
            )

        self.assertIn(
            "dynamic_sizing",
            result,
        )
        self.assertIn(
            "portfolio_exposure",
            result,
        )
        self.assertTrue(
            result[
                "portfolio_exposure"
            ]["allowed"]
        )
        self.assertLessEqual(
            result[
                "dynamic_sizing"
            ]["recommended_position_usdt"],
            7.5,
        )

    def test_existing_position_adds_exposure_block(self):
        with patch(
            "app.trader.auto_testnet_runner."
            "calculate_confidence",
            return_value={
                "decision": "REJECT",
                "adjusted_confidence_score": 90.0,
            },
        ):
            result = asyncio.run(
                _evaluate_candidate_for_selection(
                    sample_candidate(),
                    quantity=None,
                    balance=30.0,
                    risk_percent=1.0,
                    leverage=5.0,
                    current_daily_pnl=0.0,
                    open_positions_count=1,
                    open_positions=[
                        {
                            "symbol": "BTCUSDT",
                            "positionAmt": "0.001",
                            "markPrice": "60000",
                        }
                    ],
                )
            )

        self.assertFalse(
            result[
                "portfolio_exposure"
            ]["allowed"]
        )
        self.assertTrue(
            any(
                reason.startswith(
                    "Portfolio Exposure:"
                )
                for reason in result[
                    "block_reasons"
                ]
            )
        )


if __name__ == "__main__":
    unittest.main()
