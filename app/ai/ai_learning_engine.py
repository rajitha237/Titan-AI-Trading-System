"""TitanAI v26 evidence-based AI learning engine.

The engine learns only from completed trades. It remains advisory until a
minimum sample exists and applies conservative confidence adjustments.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.trader.persistent_trade_state import list_completed_trades

try:
    from app.learning.experience_store import list_experiences
except ImportError:  # Backward compatibility during staged installation.
    list_experiences = None

MIN_TRADES_FOR_ADJUSTMENT = 5
MIN_TRADES_FOR_BLOCK = 10
MAX_CONFIDENCE_ADJUSTMENT = 10.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _session_name(value: str | None) -> str:
    parsed = _parse_time(value)
    if parsed is None:
        return "UNKNOWN"
    hour = parsed.astimezone(timezone.utc).hour
    if 0 <= hour < 8:
        return "ASIA"
    if 8 <= hour < 13:
        return "LONDON"
    if 13 <= hour < 21:
        return "NEW_YORK"
    return "LATE_US"


def _metrics(trades: list[dict]) -> dict:
    pnls = [_safe_float(item.get("net_pnl")) for item in trades]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    count = len(trades)

    return {
        "trade_count": count,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": count - len(wins) - len(losses),
        "win_rate_percent": (len(wins) / count * 100.0) if count else 0.0,
        "net_pnl": sum(pnls),
        "average_net_pnl": (sum(pnls) / count) if count else 0.0,
        "profit_factor": (
            gross_profit / gross_loss if gross_loss > 0
            else (999.0 if gross_profit > 0 else 0.0)
        ),
    }


def build_learning_snapshot(*, limit: int = 5000) -> dict:
    trades = list_completed_trades(limit=max(1, min(int(limit), 10000)))
    symbol_groups: dict[str, list[dict]] = defaultdict(list)
    side_groups: dict[str, list[dict]] = defaultdict(list)
    session_groups: dict[str, list[dict]] = defaultdict(list)

    for trade in trades:
        symbol = str(trade.get("symbol", "")).upper()
        side = str(trade.get("side", "")).upper()
        session = _session_name(trade.get("closed_at"))
        if symbol:
            symbol_groups[symbol].append(trade)
        if side in {"BUY", "SELL"}:
            side_groups[side].append(trade)
        session_groups[session].append(trade)

    experience_count = 0
    if list_experiences is not None:
        try:
            experience_count = len(
                list_experiences(limit=max(1, min(int(limit), 10000)))
            )
        except Exception:
            experience_count = 0

    return {
        "status": "success",
        "version": "v26.1",
        "experience_learning_version": "experience_v1",
        "experience_record_count": experience_count,
        "overall": _metrics(trades),
        "by_symbol": {
            key: _metrics(value) for key, value in sorted(symbol_groups.items())
        },
        "by_side": {
            key: _metrics(value) for key, value in sorted(side_groups.items())
        },
        "by_session": {
            key: _metrics(value) for key, value in sorted(session_groups.items())
        },
    }


def evaluate_candidate_learning(
    *,
    symbol: str,
    side: str,
    base_confidence_score: float = 0.0,
    now: datetime | None = None,
) -> dict:
    """Return a conservative historical-performance adjustment.

    BLOCK requires at least 10 directly relevant trades and clearly poor
    performance. Before that, the result is ALLOW or WATCH.
    """
    symbol = str(symbol).upper()
    side = str(side).upper()
    now = now or datetime.now(timezone.utc)
    snapshot = build_learning_snapshot()

    symbol_metrics = snapshot["by_symbol"].get(symbol, _metrics([]))
    side_metrics = snapshot["by_side"].get(side, _metrics([]))
    session = _session_name(now.isoformat())
    session_metrics = snapshot["by_session"].get(session, _metrics([]))

    relevant_count = symbol_metrics["trade_count"]
    adjustment = 0.0
    reasons: list[str] = []

    if relevant_count >= MIN_TRADES_FOR_ADJUSTMENT:
        win_rate = symbol_metrics["win_rate_percent"]
        profit_factor = symbol_metrics["profit_factor"]
        average = symbol_metrics["average_net_pnl"]

        if win_rate >= 60 and profit_factor >= 1.25 and average > 0:
            adjustment += 6.0
            reasons.append("Symbol history is consistently profitable")
        elif win_rate < 40 and profit_factor < 0.8 and average < 0:
            adjustment -= 8.0
            reasons.append("Symbol history is consistently unprofitable")
        elif average > 0:
            adjustment += 2.0
            reasons.append("Symbol average net PnL is positive")
        elif average < 0:
            adjustment -= 2.0
            reasons.append("Symbol average net PnL is negative")
    else:
        reasons.append(
            f"Insufficient symbol history: {relevant_count}/"
            f"{MIN_TRADES_FOR_ADJUSTMENT}"
        )

    if side_metrics["trade_count"] >= MIN_TRADES_FOR_ADJUSTMENT:
        if side_metrics["win_rate_percent"] >= 58:
            adjustment += 2.0
            reasons.append(f"{side} direction has performed well")
        elif side_metrics["win_rate_percent"] < 38:
            adjustment -= 2.0
            reasons.append(f"{side} direction has performed poorly")

    if session_metrics["trade_count"] >= MIN_TRADES_FOR_ADJUSTMENT:
        if session_metrics["average_net_pnl"] > 0:
            adjustment += 1.0
            reasons.append(f"{session} session average is positive")
        elif session_metrics["average_net_pnl"] < 0:
            adjustment -= 1.0
            reasons.append(f"{session} session average is negative")

    adjustment = max(
        -MAX_CONFIDENCE_ADJUSTMENT,
        min(MAX_CONFIDENCE_ADJUSTMENT, adjustment),
    )
    adjusted_confidence = max(
        0.0,
        min(100.0, _safe_float(base_confidence_score) + adjustment),
    )

    decision = "ALLOW"
    if relevant_count < MIN_TRADES_FOR_ADJUSTMENT:
        decision = "WATCH"
    elif (
        relevant_count >= MIN_TRADES_FOR_BLOCK
        and symbol_metrics["win_rate_percent"] < 35
        and symbol_metrics["profit_factor"] < 0.65
        and symbol_metrics["net_pnl"] < 0
    ):
        decision = "BLOCK"
        reasons.append("Minimum sample reached with materially poor performance")
    elif adjustment < 0:
        decision = "WATCH"

    return {
        "status": "success",
        "version": "v26",
        "decision": decision,
        "allowed": decision != "BLOCK",
        "symbol": symbol,
        "side": side,
        "session": session,
        "base_confidence_score": _safe_float(base_confidence_score),
        "confidence_adjustment": adjustment,
        "adjusted_confidence_score": adjusted_confidence,
        "sample_size": relevant_count,
        "symbol_metrics": symbol_metrics,
        "side_metrics": side_metrics,
        "session_metrics": session_metrics,
        "reasons": reasons,
        "safety": {
            "minimum_trades_for_adjustment": MIN_TRADES_FOR_ADJUSTMENT,
            "minimum_trades_for_block": MIN_TRADES_FOR_BLOCK,
            "maximum_confidence_adjustment": MAX_CONFIDENCE_ADJUSTMENT,
        },
    }