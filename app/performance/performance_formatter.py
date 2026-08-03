"""TitanAI Performance Formatter v34."""

from __future__ import annotations


def format_performance_summary(
    dashboard: dict | None,
) -> str:
    dashboard = (
        dashboard
        if isinstance(
            dashboard,
            dict,
        )
        else {}
    )

    stats = dashboard.get(
        "trade_statistics",
        {},
    )
    drawdown = dashboard.get(
        "drawdown",
        {},
    )

    return (
        "TitanAI Performance "
        f"trades={stats.get('trade_count', 0)} "
        f"net_pnl={stats.get('net_pnl', 0.0)} "
        f"win_rate={stats.get('win_rate_percent', 0.0)}% "
        f"max_dd={drawdown.get('maximum_drawdown_percent', 0.0)}%"
    )
