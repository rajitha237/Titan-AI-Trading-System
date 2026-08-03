"""TitanAI Drawdown Analyzer v34."""

from __future__ import annotations

from app.performance.performance_metrics import (
    safe_float,
)


def analyze_drawdown(
    equity_points: list[dict] | None,
) -> dict:
    peak_equity = None
    maximum_drawdown = 0.0
    maximum_drawdown_percent = 0.0
    current_drawdown = 0.0
    current_drawdown_percent = 0.0
    drawdowns = []

    for point in equity_points or []:
        if not isinstance(point, dict):
            continue

        equity = safe_float(
            point.get("equity")
        )

        if (
            peak_equity is None
            or equity > peak_equity
        ):
            peak_equity = equity

        drawdown = (
            peak_equity - equity
            if peak_equity is not None
            else 0.0
        )

        drawdown_percent = (
            drawdown
            / abs(peak_equity)
            * 100.0
            if peak_equity not in {
                None,
                0.0,
            }
            else 0.0
        )

        maximum_drawdown = max(
            maximum_drawdown,
            drawdown,
        )
        maximum_drawdown_percent = max(
            maximum_drawdown_percent,
            drawdown_percent,
        )

        current_drawdown = drawdown
        current_drawdown_percent = (
            drawdown_percent
        )

        drawdowns.append(
            {
                "index": point.get(
                    "index"
                ),
                "equity": equity,
                "peak_equity": (
                    peak_equity
                ),
                "drawdown": drawdown,
                "drawdown_percent": (
                    drawdown_percent
                ),
            }
        )

    return {
        "status": "success",
        "version": "v34",
        "peak_equity": (
            peak_equity
            if peak_equity is not None
            else 0.0
        ),
        "maximum_drawdown": (
            maximum_drawdown
        ),
        "maximum_drawdown_percent": (
            maximum_drawdown_percent
        ),
        "current_drawdown": (
            current_drawdown
        ),
        "current_drawdown_percent": (
            current_drawdown_percent
        ),
        "drawdowns": drawdowns,
    }
