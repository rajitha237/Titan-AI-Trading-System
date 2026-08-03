"""Shared statistics helpers for TitanAI Self-Learning v2."""
from __future__ import annotations
from collections import defaultdict
from typing import Any, Callable, Iterable

def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return default
        return number
    except (TypeError, ValueError):
        return default

def sample_adjustment_cap(sample_size: int) -> float:
    sample_size = max(0, int(sample_size))
    if sample_size < 10:
        return 0.0
    if sample_size < 20:
        return 1.0
    if sample_size < 50:
        return 3.0
    return 5.0

def performance_metrics(experiences: Iterable[dict]) -> dict:
    items = list(experiences)
    pnls = [safe_float(item.get("net_pnl")) for item in items]
    wins = [value for value in pnls if value > 0]
    losses = [value for value in pnls if value < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    count = len(items)
    return {
        "trade_count": count,
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": count - len(wins) - len(losses),
        "win_rate_percent": (len(wins) / count * 100.0) if count else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "net_pnl": sum(pnls),
        "average_net_pnl": (sum(pnls) / count) if count else 0.0,
        "profit_factor": (
            gross_profit / gross_loss
            if gross_loss > 0
            else (999.0 if gross_profit > 0 else 0.0)
        ),
    }

def bounded_performance_adjustment(metrics: dict) -> dict:
    sample_size = int(metrics.get("trade_count", 0) or 0)
    cap = sample_adjustment_cap(sample_size)
    if cap <= 0:
        return {
            "sample_size": sample_size,
            "cap": 0.0,
            "raw_adjustment": 0.0,
            "adjustment": 0.0,
            "decision": "INSUFFICIENT_SAMPLE",
            "reasons": [f"Insufficient sample: {sample_size}/10"],
        }
    win_rate = safe_float(metrics.get("win_rate_percent"))
    profit_factor = safe_float(metrics.get("profit_factor"))
    average = safe_float(metrics.get("average_net_pnl"))
    raw = 0.0
    reasons = []
    if win_rate >= 65 and profit_factor >= 1.50 and average > 0:
        raw = 5.0
        reasons.append("Historical performance is strongly positive")
    elif win_rate >= 58 and profit_factor >= 1.20 and average > 0:
        raw = 3.0
        reasons.append("Historical performance is positive")
    elif win_rate >= 52 and average > 0:
        raw = 1.5
        reasons.append("Historical performance is mildly positive")
    elif win_rate < 35 and profit_factor < 0.70 and average < 0:
        raw = -5.0
        reasons.append("Historical performance is strongly negative")
    elif win_rate < 42 and profit_factor < 0.90 and average < 0:
        raw = -3.0
        reasons.append("Historical performance is negative")
    elif average < 0:
        raw = -1.5
        reasons.append("Historical average PnL is negative")
    else:
        reasons.append("Historical performance is mixed")
    adjustment = max(-cap, min(cap, raw))
    return {
        "sample_size": sample_size,
        "cap": cap,
        "raw_adjustment": raw,
        "adjustment": adjustment,
        "decision": "SUPPORT" if adjustment > 0 else "OPPOSE" if adjustment < 0 else "NEUTRAL",
        "reasons": reasons,
    }

def group_metrics(experiences: Iterable[dict], key_builder: Callable[[dict], str]) -> dict[str, dict]:
    groups = defaultdict(list)
    for item in experiences:
        key = str(key_builder(item) or "UNKNOWN").upper()
        groups[key].append(item)
    return {key: performance_metrics(values) for key, values in sorted(groups.items())}
