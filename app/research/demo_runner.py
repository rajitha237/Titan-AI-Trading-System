"""TitanAI Research Engine v2 demo runner."""

from __future__ import annotations

import argparse
import asyncio
import json

from app.research.backtester import run_backtest
from app.research.config import ResearchConfig
from app.research.data_store import save_dataset
from app.research.dataset_split import chronological_split
from app.research.feature_engine import generate_features
from app.research.historical_collector import fetch_recent_months
from app.research.market_regime_detector import detect_market_regime
from app.research.optimizer import optimize_on_train_validate
from app.research.pattern_similarity import find_similar_patterns
from app.research.performance_report import summarize_backtest
from app.research.probability_engine import estimate_trade_probability
from app.research.research_store import save_report
from app.research.sk_system_engine import calculate_sk_features
from app.research.strategy import (
    StrategyParameters,
    build_strategy_signals,
)
from app.research.walk_forward import run_walk_forward


async def run_demo(config: ResearchConfig) -> dict:
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.report_dir.mkdir(parents=True, exist_ok=True)

    results = []
    errors = []

    backtest_kwargs = {
        "initial_balance": config.initial_balance,
        "risk_per_trade_percent": (
            config.risk_per_trade_percent
        ),
        "fee_rate": config.fee_rate,
        "slippage_rate": config.slippage_rate,
    }

    for symbol in config.symbols:
        for timeframe in config.timeframes:
            print(f"[DOWNLOAD] {symbol} {timeframe}")
            try:
                candles = await fetch_recent_months(
                    symbol,
                    timeframe,
                    months=config.months,
                    limit=config.request_limit,
                    timeout=config.request_timeout_seconds,
                )
                if candles.empty:
                    raise RuntimeError("No candles returned")

                save_dataset(
                    candles,
                    config.data_dir,
                    symbol,
                    timeframe,
                )

                features = generate_features(candles)
                features = detect_market_regime(features)
                features = calculate_sk_features(features)
                save_dataset(
                    features,
                    config.data_dir,
                    symbol,
                    timeframe,
                    kind="features_v2",
                )

                split = chronological_split(
                    features,
                    train_fraction=config.train_fraction,
                    validation_fraction=(
                        config.validation_fraction
                    ),
                )

                optimization = optimize_on_train_validate(
                    split["train"],
                    split["validation"],
                    symbol=symbol,
                    timeframe=timeframe,
                    backtest_kwargs=backtest_kwargs,
                    minimum_validation_trades=(
                        config.minimum_validation_trades
                    ),
                )
                best = optimization.get("best")
                if not best:
                    raise RuntimeError(
                        "Parameter optimization produced no candidate"
                    )

                parameters = StrategyParameters(
                    **best["parameters"]
                )
                test_signals = build_strategy_signals(
                    split["test"],
                    parameters=parameters,
                )
                test_backtest = run_backtest(
                    test_signals,
                    symbol=symbol,
                    timeframe=timeframe,
                    **backtest_kwargs,
                )
                test_report = summarize_backtest(
                    test_backtest
                )

                walk_forward = run_walk_forward(
                    features,
                    symbol=symbol,
                    timeframe=timeframe,
                    parameters=parameters,
                    backtest_kwargs=backtest_kwargs,
                )
                probability = estimate_trade_probability(
                    test_report
                )
                similarity = find_similar_patterns(
                    features,
                    top_k=100,
                )

                approved = (
                    best["validation_passed"]
                    and test_report["trade_count"]
                    >= config.minimum_test_trades
                    and test_report["expectancy_r"] > 0
                    and test_report["profit_factor"] > 1.0
                    and test_report[
                        "maximum_drawdown_percent"
                    ]
                    <= config.maximum_test_drawdown_percent
                    and walk_forward.get(
                        "positive_fold_ratio",
                        0.0,
                    )
                    >= 2 / 3
                )

                report = {
                    "version": "v2",
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "approved": approved,
                    "parameters": best["parameters"],
                    "train_report": best["train_report"],
                    "validation_report": (
                        best["validation_report"]
                    ),
                    "test_report": test_report,
                    "walk_forward": walk_forward,
                    "probability": probability,
                    "pattern_similarity": similarity,
                    "safety": {
                        "selection_basis": (
                            "parameters selected on train and "
                            "validation only"
                        ),
                        "test_data_used_for_selection": False,
                    },
                }
                save_report(
                    config.database_path,
                    report,
                )
                results.append(report)

                print(
                    f"[DONE] {symbol} {timeframe} | "
                    f"Approved={approved} | "
                    f"Test Trades={test_report['trade_count']} | "
                    f"WR={test_report['win_rate_percent']:.2f}% | "
                    f"PF={test_report['profit_factor']:.2f} | "
                    f"Exp={test_report['expectancy_r']:.3f}R | "
                    f"WF={walk_forward.get('positive_fold_ratio', 0):.2f}"
                )
            except Exception as error:
                errors.append(
                    {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "error": str(error),
                    }
                )
                print(
                    f"[ERROR] {symbol} {timeframe}: {error}"
                )

    ranked = sorted(
        results,
        key=lambda item: (
            item["approved"],
            item["test_report"]["expectancy_r"],
            item["test_report"]["profit_factor"],
            -item["test_report"][
                "maximum_drawdown_percent"
            ],
        ),
        reverse=True,
    )

    output = {
        "status": "success" if results else "failed",
        "version": "v2",
        "approved_count": sum(
            1 for item in results if item["approved"]
        ),
        "results": ranked,
        "best_setup": ranked[0] if ranked else None,
        "errors": errors,
    }

    path = config.report_dir / "demo_report_v2.json"
    path.write_text(
        json.dumps(output, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nReport saved: {path}")
    if ranked:
        print(
            "\nBEST V2 SETUP\n"
            + json.dumps(
                ranked[0],
                indent=2,
                default=str,
            )
        )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--symbols",
        default="BTCUSDT,ETHUSDT,SOLUSDT",
    )
    parser.add_argument(
        "--timeframes",
        default="15m,1h",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
    )
    args = parser.parse_args()

    config = ResearchConfig(
        symbols=tuple(
            item.strip().upper()
            for item in args.symbols.split(",")
            if item.strip()
        ),
        timeframes=tuple(
            item.strip()
            for item in args.timeframes.split(",")
            if item.strip()
        ),
        months=max(2, args.months),
    )
    asyncio.run(run_demo(config))


if __name__ == "__main__":
    main()
