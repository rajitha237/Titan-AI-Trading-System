"""Combine institutional evidence with bounded experience-memory input."""

from __future__ import annotations

from typing import Any


MAX_PATTERN_ADJUSTMENT = 6.0


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)

        if number != number:
            return default

        if number in {
            float("inf"),
            float("-inf"),
        }:
            return default

        return number

    except (TypeError, ValueError):
        return default


def build_adaptive_score(
    *,
    ai_score: dict,
    regime: dict,
    strategy: dict,
    research: dict,
    probabilities: dict,
    pattern_memory: dict | None = None,
) -> dict:
    """Return institutional score with advisory pattern-memory adjustment.

    Pattern Memory is bounded and cannot remove existing hard blocks.
    """
    pattern_memory = (
        pattern_memory
        if isinstance(pattern_memory, dict)
        else {}
    )

    raw = _safe_float(
        ai_score.get("score"),
        50.0,
    )
    direction = (
        "BUY"
        if raw >= 50
        else "SELL"
    )
    directional_raw = (
        raw
        if direction == "BUY"
        else 100.0 - raw
    )

    regime_component = (
        _safe_float(regime.get("confidence"))
        if str(
            regime.get("direction", "")
        ).upper()
        == direction
        else 0.0
    )

    strategy_component = (
        _safe_float(strategy.get("strategy_score"))
        if str(
            strategy.get("direction", "")
        ).upper()
        == direction
        else 0.0
    )

    research_component = _safe_float(
        research.get("score"),
        50.0,
    )

    probability_key = (
        "long_probability"
        if direction == "BUY"
        else "short_probability"
    )
    probability_component = _safe_float(
        probabilities.get(probability_key),
        0.0,
    )

    institutional_base_score = (
        directional_raw * 0.45
        + regime_component * 0.15
        + strategy_component * 0.12
        + research_component * 0.13
        + probability_component * 0.15
    )

    pattern_sample_size = max(
        0,
        int(
            _safe_float(
                pattern_memory.get("sample_size"),
                0.0,
            )
        ),
    )

    requested_pattern_adjustment = _safe_float(
        pattern_memory.get(
            "confidence_adjustment"
        ),
        0.0,
    )

    pattern_adjustment = max(
        -MAX_PATTERN_ADJUSTMENT,
        min(
            MAX_PATTERN_ADJUSTMENT,
            requested_pattern_adjustment,
        ),
    )

    # A tiny/empty sample must never influence live scoring.
    if pattern_sample_size < 5:
        pattern_adjustment = 0.0

    final = institutional_base_score + pattern_adjustment
    final = max(
        0.0,
        min(
            100.0,
            final,
        ),
    )

    blocks: list[str] = []

    if research.get("hard_block"):
        blocks.append(
            "Historical unseen-test evidence strongly opposes this setup"
        )

    if not regime.get("tradeable"):
        blocks.append(
            "Live market regime is not tradeable"
        )

    if (
        strategy.get("selected_strategy")
        == "NO_TRADE"
    ):
        blocks.append(
            "No institutional strategy matches the current regime"
        )

    if not probabilities.get(
        "institutional_threshold_passed"
    ):
        blocks.append(
            "Institutional probability threshold did not pass"
        )

    action = (
        "REJECT"
        if blocks
        else (
            "TRADE"
            if final >= 82
            else (
                "SMALL_TRADE"
                if final >= 75
                else "WATCH"
            )
        )
    )

    allowed = action in {
        "TRADE",
        "SMALL_TRADE",
    }

    adjusted = dict(ai_score)
    adjusted["raw_score"] = raw
    adjusted["score"] = round(
        final
        if direction == "BUY"
        else 100.0 - final,
        2,
    )
    adjusted[
        "institutional_directional_score"
    ] = round(
        final,
        2,
    )
    adjusted["institutional_action"] = action
    adjusted[
        "institutional_block_reasons"
    ] = blocks
    adjusted[
        "pattern_memory_adjustment"
    ] = round(
        pattern_adjustment,
        2,
    )
    adjusted[
        "pattern_memory_sample_size"
    ] = pattern_sample_size
    adjusted[
        "institutional_breakdown"
    ] = {
        "live": round(
            directional_raw,
            2,
        ),
        "regime": round(
            regime_component,
            2,
        ),
        "strategy": round(
            strategy_component,
            2,
        ),
        "research": round(
            research_component,
            2,
        ),
        "probability": round(
            probability_component,
            2,
        ),
        "pattern_memory": round(
            pattern_adjustment,
            2,
        ),
    }

    return {
        "status": "ready",
        "version": "pattern_memory_v1",
        "direction": direction,
        "base_score": round(
            institutional_base_score,
            2,
        ),
        "pattern_adjustment": round(
            pattern_adjustment,
            2,
        ),
        "final_score": round(
            final,
            2,
        ),
        "action": action,
        "allowed": allowed,
        "block_reasons": blocks,
        "pattern_memory": pattern_memory,
        "adjusted_ai_score": adjusted,
    }
