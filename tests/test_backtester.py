"""Offline backtester and analytics tests."""

from __future__ import annotations

import unittest

from app.research.backtester import run_backtest
from app.research.feature_engine import generate_features
from app.research.market_regime_detector import detect_market_regime
from app.research.performance_report import summarize_backtest
from app.research.sk_system_engine import calculate_sk_features
from app.research.strategy import StrategyParameters, build_strategy_signals

from tests.helpers import make_candles


class BacktesterTests(unittest.TestCase):
    def test_backtest_result_schema(self):
        frame = generate_features(make_candles())
        frame = detect_market_regime(frame)
        frame = calculate_sk_features(frame)
        frame = build_strategy_signals(
            frame,
            parameters=StrategyParameters(
                minimum_score=60,
                minimum_adx=0,
                minimum_volume_ratio=0,
                minimum_abs_delta=0,
                require_sk=False,
                require_bos=False,
                allowed_sessions=(
                    "ASIA",
                    "LONDON",
                    "NEW_YORK",
                    "LATE_US",
                ),
            ),
        )

        result = run_backtest(
            frame,
            symbol="BTCUSDT",
            timeframe="15m",
            initial_balance=1000,
        )
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertIn("trades", result)
        self.assertIn("equity_curve", result)
        self.assertGreaterEqual(result["final_balance"], 0)

        report = summarize_backtest(result)
        required = {
            "trade_count",
            "win_rate_percent",
            "profit_factor",
            "expectancy_r",
            "maximum_drawdown_percent",
            "final_balance",
        }
        self.assertTrue(required.issubset(report))
        self.assertGreaterEqual(report["win_rate_percent"], 0)
        self.assertLessEqual(report["win_rate_percent"], 100)


if __name__ == "__main__":
    unittest.main()
