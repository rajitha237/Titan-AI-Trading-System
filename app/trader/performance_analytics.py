"""TitanAI v24 completed-trade performance analytics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.trader.persistent_trade_state import list_completed_trades


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def build_performance_snapshot(
    *,
    hours: int = 24,
    symbol: str | None = None,
) -> dict:
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=max(1, int(hours)))
    trades = list_completed_trades(
        start_time=start.isoformat(),
        end_time=now.isoformat(),
        symbol=symbol,
        limit=10000,
    )

    pnls = [_safe_float(item.get("net_pnl")) for item in trades]
    wins = [pnl for pnl in pnls if pnl > 0]
    losses = [pnl for pnl in pnls if pnl < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    total = len(trades)

    consecutive_losses = 0
    for trade in trades:  # newest first
        if _safe_float(trade.get("net_pnl")) < 0:
            consecutive_losses += 1
        else:
            break

    return {
        "status": "success",
        "window_hours": max(1, int(hours)),
        "symbol": symbol.upper() if symbol else None,
        "trade_count": total,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": total - len(wins) - len(losses),
        "win_rate_percent": (len(wins) / total * 100.0) if total else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_pnl": sum(pnls),
        "profit_factor": (
            gross_profit / gross_loss if gross_loss > 0 else
            (float("inf") if gross_profit > 0 else 0.0)
        ),
        "average_net_pnl": (sum(pnls) / total) if total else 0.0,
        "largest_win": max(wins) if wins else 0.0,
        "largest_loss": min(losses) if losses else 0.0,
        "consecutive_losses": consecutive_losses,
        "start_time": start.isoformat(),
        "end_time": now.isoformat(),
    }