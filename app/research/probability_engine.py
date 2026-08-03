"""Conservative probability estimate from unseen-test evidence."""

from __future__ import annotations

from math import sqrt


def wilson_lower_bound(
    wins: int,
    total: int,
    *,
    z: float = 1.96,
) -> float:
    if total <= 0:
        return 0.0
    proportion = wins / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * sqrt(
        (proportion * (1 - proportion) + z * z / (4 * total))
        / total
    )
    return max(0.0, (centre - margin) / denominator)


def estimate_trade_probability(report: dict) -> dict:
    total = int(report.get("trade_count", 0))
    wins = int(report.get("wins", 0))
    raw = wins / total * 100 if total else 0.0
    lower = wilson_lower_bound(wins, total) * 100

    return {
        "sample_size": total,
        "raw_win_rate_percent": raw,
        "confidence_lower_bound_percent": lower,
        "method": "Wilson 95% lower confidence bound",
    }
