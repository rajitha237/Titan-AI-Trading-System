"""Parameter sweep with validation-first selection."""

from __future__ import annotations

from dataclasses import asdict
from itertools import product

import pandas as pd

from app.research.backtester import run_backtest
from app.research.performance_report import summarize_backtest
from app.research.strategy import (
    StrategyParameters,
    build_strategy_signals,
)


def generate_parameter_grid() -> list[StrategyParameters]:
    grid = []
    for values in product(
        (78.0, 82.0, 86.0),
        (20.0, 24.0, 28.0),
        (0.9, 1.1, 1.3),
        (0.03, 0.08, 0.15),
        (True, False),
        (False, True),
    ):
        (
            score,
            adx,
            volume,
            delta,
            require_sk,
            require_bos,
        ) = values
        grid.append(
            StrategyParameters(
                minimum_score=score,
                minimum_adx=adx,
                minimum_volume_ratio=volume,
                minimum_abs_delta=delta,
                require_sk=require_sk,
                require_bos=require_bos,
            )
        )
    return grid


def evaluate_parameters(
    frame: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    parameters: StrategyParameters,
    backtest_kwargs: dict,
) -> dict:
    signals = build_strategy_signals(
        frame,
        parameters=parameters,
    )
    backtest = run_backtest(
        signals,
        symbol=symbol,
        timeframe=timeframe,
        **backtest_kwargs,
    )
    report = summarize_backtest(backtest)
    return {
        "parameters": asdict(parameters),
        "report": report,
    }


def optimize_on_train_validate(
    train: pd.DataFrame,
    validation: pd.DataFrame,
    *,
    symbol: str,
    timeframe: str,
    backtest_kwargs: dict,
    minimum_validation_trades: int = 8,
) -> dict:
    candidates = []

    for parameters in generate_parameter_grid():
        train_result = evaluate_parameters(
            train,
            symbol=symbol,
            timeframe=timeframe,
            parameters=parameters,
            backtest_kwargs=backtest_kwargs,
        )
        validation_result = evaluate_parameters(
            validation,
            symbol=symbol,
            timeframe=timeframe,
            parameters=parameters,
            backtest_kwargs=backtest_kwargs,
        )

        train_report = train_result["report"]
        validation_report = validation_result["report"]

        valid = (
            validation_report["trade_count"]
            >= minimum_validation_trades
            and validation_report["expectancy_r"] > 0
            and validation_report["profit_factor"] > 1.0
        )

        stability_penalty = abs(
            train_report["expectancy_r"]
            - validation_report["expectancy_r"]
        )
        objective = (
            validation_report["expectancy_r"] * 3
            + min(validation_report["profit_factor"], 3.0)
            - validation_report[
                "maximum_drawdown_percent"
            ] / 20
            - stability_penalty
        )

        candidates.append(
            {
                "parameters": train_result["parameters"],
                "train_report": train_report,
                "validation_report": validation_report,
                "validation_passed": valid,
                "objective": objective,
            }
        )

    ranked = sorted(
        candidates,
        key=lambda item: (
            item["validation_passed"],
            item["objective"],
        ),
        reverse=True,
    )

    return {
        "best": ranked[0] if ranked else None,
        "ranked": ranked,
    }
