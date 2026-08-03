"""TitanAI Equity Curve v34."""

from __future__ import annotations

from typing import Any

from app.performance.performance_metrics import (
    safe_float,
)


def build_equity_curve(
    trades: list[dict] | None,
    *,
    starting_equity: float = 0.0,
) -> dict:
    equity = safe_float(
        starting_equity
    )
    curve = [
        {
            "index": 0,
            "equity": equity,
            "pnl": 0.0,
        }
    ]

    for index, trade in enumerate(
        trades or [],
        start=1,
    ):
        if not isinstance(trade, dict):
            continue

        pnl = 0.0

        for key in (
            "net_pnl",
            "realized_pnl",
            "pnl",
            "profit",
        ):
            if key in trade:
                pnl = safe_float(
                    trade.get(key)
                )
                break

        equity += pnl

        curve.append(
            {
                "index": index,
                "equity": round(
                    equity,
                    8,
                ),
                "pnl": round(
                    pnl,
                    8,
                ),
                "timestamp": trade.get(
                    "closed_at",
                    trade.get(
                        "timestamp"
                    ),
                ),
                "symbol": trade.get(
                    "symbol"
                ),
            }
        )

    return {
        "status": "success",
        "version": "v34",
        "starting_equity": (
            safe_float(
                starting_equity
            )
        ),
        "ending_equity": equity,
        "points": curve,
    }
