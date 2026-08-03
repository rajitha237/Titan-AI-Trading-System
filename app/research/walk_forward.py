"""Simple anchored walk-forward robustness test."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from app.research.backtester import run_backtest
from app.research.performance_report import summarize_backtest
from app.research.strategy import (
    StrategyParameters,
    build_strategy_signals,
)


def run_walk_forward(
    frame: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    parameters: StrategyParameters,
    backtest_kwargs: dict,
    folds: int = 3,
) -> dict:
    if len(frame) < 300:
        return {
            "status": "insufficient_data",
            "folds": [],
            "positive_fold_ratio": 0.0,
        }

    fold_size = len(frame) // (folds + 1)
    reports = []

    for fold in range(1, folds + 1):
        start = fold * fold_size
        end = min(start + fold_size, len(frame))
        segment = frame.iloc[start:end].copy()
        signals = build_strategy_signals(
            segment,
            parameters=parameters,
        )
        backtest = run_backtest(
            signals,
            symbol=symbol,
            timeframe=timeframe,
            **backtest_kwargs,
        )
        reports.append(summarize_backtest(backtest))

    positive = sum(
        1
        for report in reports
        if report["expectancy_r"] > 0
        and report["profit_factor"] > 1
    )

    return {
        "status": "success",
        "parameters": asdict(parameters),
        "folds": reports,
        "positive_fold_ratio": (
            positive / len(reports) if reports else 0.0
        ),
    }
