"""TitanAI Trade Statistics v34."""

from __future__ import annotations

from typing import Any

from app.performance.performance_metrics import (
    calculate_expectancy,
    calculate_profit_factor,
    safe_float,
)


def _extract_pnl(
    trade: Any,
) -> float:
    if not isinstance(trade, dict):
        return 0.0

    for key in (
        "net_pnl",
        "realized_pnl",
        "pnl",
        "profit",
    ):
        if key in trade:
            return safe_float(
                trade.get(key)
            )

    return 0.0


def _current_streak(
    pnls: list[float],
) -> tuple[int, int]:
    if not pnls:
        return 0, 0

    last = pnls[-1]

    if last > 0:
        count = 0
        for value in reversed(pnls):
            if value > 0:
                count += 1
            else:
                break
        return count, 0

    if last < 0:
        count = 0
        for value in reversed(pnls):
            if value < 0:
                count += 1
            else:
                break
        return 0, count

    return 0, 0


def _maximum_streaks(
    pnls: list[float],
) -> tuple[int, int]:
    max_wins = 0
    max_losses = 0
    current_wins = 0
    current_losses = 0

    for value in pnls:
        if value > 0:
            current_wins += 1
            current_losses = 0
            max_wins = max(
                max_wins,
                current_wins,
            )
        elif value < 0:
            current_losses += 1
            current_wins = 0
            max_losses = max(
                max_losses,
                current_losses,
            )
        else:
            current_wins = 0
            current_losses = 0

    return max_wins, max_losses


def calculate_trade_statistics(
    trades: list[dict] | None,
) -> dict:
    valid_trades = [
        trade
        for trade in (trades or [])
        if isinstance(trade, dict)
    ]

    pnls = [
        _extract_pnl(trade)
        for trade in valid_trades
    ]

    wins = [
        value
        for value in pnls
        if value > 0
    ]
    losses = [
        value
        for value in pnls
        if value < 0
    ]
    breakeven = [
        value
        for value in pnls
        if value == 0
    ]

    trade_count = len(pnls)
    win_count = len(wins)
    loss_count = len(losses)
    breakeven_count = len(
        breakeven
    )

    gross_profit = sum(wins)
    gross_loss = sum(losses)
    net_pnl = sum(pnls)

    win_rate = (
        win_count / trade_count
        if trade_count
        else 0.0
    )
    loss_rate = (
        loss_count / trade_count
        if trade_count
        else 0.0
    )

    average_win = (
        gross_profit / win_count
        if win_count
        else 0.0
    )
    average_loss = (
        gross_loss / loss_count
        if loss_count
        else 0.0
    )

    current_win_streak, (
        current_loss_streak
    ) = _current_streak(pnls)

    max_win_streak, (
        max_loss_streak
    ) = _maximum_streaks(pnls)

    return {
        "status": "success",
        "version": "v34",
        "trade_count": trade_count,
        "wins": win_count,
        "losses": loss_count,
        "breakeven": breakeven_count,
        "win_rate_percent": round(
            win_rate * 100.0,
            4,
        ),
        "loss_rate_percent": round(
            loss_rate * 100.0,
            4,
        ),
        "net_pnl": round(
            net_pnl,
            8,
        ),
        "gross_profit": round(
            gross_profit,
            8,
        ),
        "gross_loss": round(
            gross_loss,
            8,
        ),
        "profit_factor": (
            calculate_profit_factor(
                gross_profit,
                gross_loss,
            )
        ),
        "average_trade": (
            net_pnl / trade_count
            if trade_count
            else 0.0
        ),
        "average_win": average_win,
        "average_loss": average_loss,
        "expectancy": (
            calculate_expectancy(
                win_rate=win_rate,
                average_win=average_win,
                loss_rate=loss_rate,
                average_loss=average_loss,
            )
        ),
        "largest_win": (
            max(wins)
            if wins
            else 0.0
        ),
        "largest_loss": (
            min(losses)
            if losses
            else 0.0
        ),
        "current_win_streak": (
            current_win_streak
        ),
        "current_loss_streak": (
            current_loss_streak
        ),
        "max_win_streak": (
            max_win_streak
        ),
        "max_loss_streak": (
            max_loss_streak
        ),
    }
