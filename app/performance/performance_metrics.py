"""TitanAI Performance Metrics v34."""

from __future__ import annotations

from typing import Any


def safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
        if (
            number != number
            or number in {
                float("inf"),
                float("-inf"),
            }
        ):
            return default
        return number
    except (TypeError, ValueError):
        return default


def calculate_profit_factor(
    gross_profit: float,
    gross_loss: float,
) -> float:
    gross_profit = max(
        0.0,
        safe_float(gross_profit),
    )
    gross_loss = abs(
        safe_float(gross_loss)
    )

    if gross_loss == 0:
        return (
            float("inf")
            if gross_profit > 0
            else 0.0
        )

    return gross_profit / gross_loss


def calculate_expectancy(
    *,
    win_rate: float,
    average_win: float,
    loss_rate: float,
    average_loss: float,
) -> float:
    return (
        safe_float(win_rate)
        * safe_float(average_win)
        - safe_float(loss_rate)
        * abs(
            safe_float(average_loss)
        )
    )


def calculate_sharpe_ratio(
    returns: list[float] | None,
    *,
    risk_free_rate: float = 0.0,
) -> float:
    values = [
        safe_float(value)
        for value in (returns or [])
    ]

    if len(values) < 2:
        return 0.0

    excess = [
        value - risk_free_rate
        for value in values
    ]

    mean_return = sum(excess) / len(excess)
    variance = sum(
        (value - mean_return) ** 2
        for value in excess
    ) / (len(excess) - 1)

    if variance <= 0:
        return 0.0

    return mean_return / (variance ** 0.5)
