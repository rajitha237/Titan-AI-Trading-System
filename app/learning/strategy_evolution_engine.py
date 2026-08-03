"""Advisory strategy performance weights from completed experiences."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.learning.experience_store import list_experiences

MIN_SAMPLE_FOR_WEIGHT = 10
MIN_WEIGHT = 0.85
MAX_WEIGHT = 1.15


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number == number else default
    except (TypeError, ValueError):
        return default


def build_strategy_evolution_snapshot(
    *,
    limit: int = 10000,
) -> dict:
    experiences = list_experiences(limit=limit)
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)

    for item in experiences:
        key = (
            str(item.get("strategy") or "UNKNOWN"),
            str(item.get("market_regime") or "UNKNOWN"),
            str(item.get("session") or "UNKNOWN"),
        )
        groups[key].append(item)

    entries: list[dict] = []
    for (strategy, regime, session), items in groups.items():
        count = len(items)
        wins = sum(
            1
            for item in items
            if str(item.get("outcome")).upper() == "WIN"
        )
        net_pnl = sum(
            _safe_float(item.get("net_pnl"))
            for item in items
        )
        win_rate = wins / count * 100.0 if count else 0.0
        average = net_pnl / count if count else 0.0

        weight = 1.0
        status = "INSUFFICIENT_SAMPLE"

        if count >= MIN_SAMPLE_FOR_WEIGHT:
            status = "ACTIVE"
            if win_rate >= 60 and average > 0:
                weight = 1.10
            elif win_rate >= 52 and average > 0:
                weight = 1.04
            elif win_rate < 38 and average < 0:
                weight = 0.88
            elif average < 0:
                weight = 0.96

        weight = max(MIN_WEIGHT, min(MAX_WEIGHT, weight))
        entries.append(
            {
                "strategy": strategy,
                "market_regime": regime,
                "session": session,
                "sample_size": count,
                "wins": wins,
                "win_rate_percent": round(win_rate, 2),
                "net_pnl": round(net_pnl, 8),
                "average_net_pnl": round(average, 8),
                "weight": weight,
                "status": status,
            }
        )

    entries.sort(
        key=lambda item: (
            item["status"] == "ACTIVE",
            item["weight"],
            item["sample_size"],
        ),
        reverse=True,
    )

    return {
        "status": "success",
        "version": "experience_v1",
        "minimum_sample_for_weight": MIN_SAMPLE_FOR_WEIGHT,
        "minimum_weight": MIN_WEIGHT,
        "maximum_weight": MAX_WEIGHT,
        "entries": entries,
    }


def get_strategy_weight(
    *,
    strategy: str,
    market_regime: str,
    session: str,
) -> dict:
    snapshot = build_strategy_evolution_snapshot()

    for item in snapshot["entries"]:
        if (
            item["strategy"] == strategy
            and item["market_regime"] == market_regime
            and item["session"] == session
        ):
            return item

    return {
        "strategy": strategy,
        "market_regime": market_regime,
        "session": session,
        "sample_size": 0,
        "weight": 1.0,
        "status": "INSUFFICIENT_SAMPLE",
    }
