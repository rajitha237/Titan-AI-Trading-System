"""TitanAI Performance Dashboard v34."""

from __future__ import annotations

from app.performance.drawdown_analyzer import (
    analyze_drawdown,
)
from app.performance.equity_curve import (
    build_equity_curve,
)
from app.performance.performance_metrics import (
    calculate_sharpe_ratio,
)
from app.performance.trade_statistics import (
    calculate_trade_statistics,
)


def build_performance_dashboard(
    *,
    trades: list[dict] | None,
    starting_equity: float = 0.0,
) -> dict:
    statistics = (
        calculate_trade_statistics(
            trades
        )
    )
    equity_curve = build_equity_curve(
        trades,
        starting_equity=starting_equity,
    )
    drawdown = analyze_drawdown(
        equity_curve.get(
            "points",
            [],
        )
    )

    returns = [
        float(
            point.get("pnl", 0.0)
        )
        for point in equity_curve.get(
            "points",
            [],
        )[1:]
    ]

    return {
        "status": "success",
        "version": "v34",
        "advisory_only": True,
        "trade_statistics": (
            statistics
        ),
        "equity_curve": equity_curve,
        "drawdown": drawdown,
        "sharpe_ratio": (
            calculate_sharpe_ratio(
                returns
            )
        ),
    }
