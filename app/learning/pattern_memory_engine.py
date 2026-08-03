"""Conservative similarity search over completed-trade experiences."""

from __future__ import annotations

from math import exp
from typing import Any

from app.learning.experience_store import list_experiences

MIN_SIMILAR_SAMPLE = 5
MAX_PATTERN_ADJUSTMENT = 6.0


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if number == number else default
    except (TypeError, ValueError):
        return default


def _categorical_score(current: Any, historical: Any) -> float:
    current_text = str(current or "UNKNOWN").upper()
    historical_text = str(historical or "UNKNOWN").upper()

    if current_text == "UNKNOWN" or historical_text == "UNKNOWN":
        return 0.25
    return 1.0 if current_text == historical_text else 0.0


def _numeric_score(
    current: Any,
    historical: Any,
    *,
    scale: float,
) -> float:
    difference = abs(
        _safe_float(current) - _safe_float(historical)
    )
    return exp(-difference / max(scale, 1e-9))


def fingerprint_similarity(
    current: dict,
    historical: dict,
) -> float:
    """Return a bounded 0..1 weighted similarity score."""
    categorical_fields = (
        "symbol",
        "side",
        "session",
        "market_regime",
        "strategy",
        "technical_trend",
        "macd_direction",
        "order_flow_pressure",
        "order_book_pressure",
        "research_decision",
    )

    categorical = [
        _categorical_score(
            current.get(field),
            historical.get(field),
        )
        for field in categorical_fields
    ]

    numeric = [
        _numeric_score(
            current.get("rsi_bucket"),
            historical.get("rsi_bucket"),
            scale=20.0,
        ),
        _numeric_score(
            current.get("adx_bucket"),
            historical.get("adx_bucket"),
            scale=15.0,
        ),
        _numeric_score(
            current.get("delta_bucket"),
            historical.get("delta_bucket"),
            scale=0.5,
        ),
    ]

    score = (
        sum(categorical) * 0.7 / len(categorical)
        + sum(numeric) * 0.3 / len(numeric)
    )
    return max(0.0, min(1.0, score))


def evaluate_pattern_memory(
    current_fingerprint: dict,
    *,
    top_k: int = 50,
    minimum_similarity: float = 0.55,
) -> dict:
    symbol = str(
        current_fingerprint.get("symbol", "")
    ).upper() or None
    side = str(
        current_fingerprint.get("side", "")
    ).upper() or None

    candidates = list_experiences(
        symbol=symbol,
        side=side,
        limit=5000,
    )

    ranked: list[tuple[float, dict]] = []
    for experience in candidates:
        similarity = fingerprint_similarity(
            current_fingerprint,
            experience.get("pattern_fingerprint") or {},
        )
        if similarity >= minimum_similarity:
            ranked.append((similarity, experience))

    ranked.sort(key=lambda item: item[0], reverse=True)
    selected = ranked[: max(1, min(int(top_k), 500))]

    weighted_total = sum(score for score, _ in selected)
    weighted_wins = sum(
        score
        for score, item in selected
        if str(item.get("outcome")).upper() == "WIN"
    )
    weighted_losses = sum(
        score
        for score, item in selected
        if str(item.get("outcome")).upper() == "LOSS"
    )
    weighted_pnl = sum(
        score * _safe_float(item.get("net_pnl"))
        for score, item in selected
    )

    sample_size = len(selected)
    win_probability = (
        weighted_wins / weighted_total * 100.0
        if weighted_total > 0
        else 0.0
    )
    average_pnl = (
        weighted_pnl / weighted_total
        if weighted_total > 0
        else 0.0
    )

    adjustment = 0.0
    decision = "WATCH"
    reasons: list[str] = []

    if sample_size < MIN_SIMILAR_SAMPLE:
        reasons.append(
            f"Insufficient similar experience: "
            f"{sample_size}/{MIN_SIMILAR_SAMPLE}"
        )
    else:
        if win_probability >= 62 and average_pnl > 0:
            adjustment = 4.0
            decision = "SUPPORT"
            reasons.append(
                "Similar completed trades show positive historical edge"
            )
        elif win_probability < 38 and average_pnl < 0:
            adjustment = -6.0
            decision = "OPPOSE"
            reasons.append(
                "Similar completed trades show materially negative edge"
            )
        elif average_pnl > 0:
            adjustment = 1.5
            decision = "SUPPORT"
            reasons.append(
                "Similar completed trades have positive average PnL"
            )
        elif average_pnl < 0:
            adjustment = -2.0
            decision = "WATCH"
            reasons.append(
                "Similar completed trades have negative average PnL"
            )
        else:
            reasons.append("Similar experience is mixed")

    adjustment = max(
        -MAX_PATTERN_ADJUSTMENT,
        min(MAX_PATTERN_ADJUSTMENT, adjustment),
    )

    return {
        "status": "success",
        "version": "experience_v1",
        "decision": decision,
        "sample_size": sample_size,
        "win_probability_percent": round(win_probability, 2),
        "average_net_pnl": round(average_pnl, 8),
        "confidence_adjustment": adjustment,
        "minimum_similarity": minimum_similarity,
        "average_similarity": round(
            sum(score for score, _ in selected) / sample_size,
            4,
        ) if sample_size else 0.0,
        "reasons": reasons,
        "matches": [
            {
                "experience_id": item.get("experience_id"),
                "trade_id": item.get("trade_id"),
                "similarity": round(score, 4),
                "outcome": item.get("outcome"),
                "net_pnl": item.get("net_pnl"),
            }
            for score, item in selected[:10]
        ],
    }
