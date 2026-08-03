"""Build stable, reporting-only learning diagnostics for runner results."""

from __future__ import annotations

from typing import Any

from app.learning.self_learning_dashboard import (
    build_self_learning_dashboard,
)


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


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


def _candidate_from_result(result: dict) -> dict:
    best_setup = _mapping(result.get("best_setup"))

    if best_setup:
        return best_setup

    scan = _mapping(result.get("scan"))
    best_setup = _mapping(scan.get("best_setup"))

    if best_setup:
        return best_setup

    attempts = result.get("candidate_attempts")

    if isinstance(attempts, list):
        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue

            candidate = _mapping(attempt.get("candidate"))

            if candidate:
                return candidate

    return {}


def build_runner_learning_diagnostics(
    result: dict | None,
) -> dict:
    """Return diagnostics without recalculating or changing any trade decision."""
    result = _mapping(result)
    candidate = _candidate_from_result(result)

    pattern_memory = _mapping(
        candidate.get(
            "pattern_memory",
            result.get("pattern_memory"),
        )
    )
    self_learning = _mapping(
        candidate.get(
            "self_learning",
            result.get("self_learning"),
        )
    )

    adaptive_score = _mapping(
        candidate.get("adaptive_score")
    )

    if not self_learning:
        self_learning = _mapping(
            adaptive_score.get("self_learning")
        )

    learning_adjustment = _safe_float(
        self_learning.get(
            "learning_adjustment",
            adaptive_score.get(
                "self_learning_adjustment",
                0.0,
            ),
        ),
        0.0,
    )

    pattern_adjustment = _safe_float(
        pattern_memory.get(
            "confidence_adjustment",
            adaptive_score.get(
                "pattern_adjustment",
                0.0,
            ),
        ),
        0.0,
    )

    if learning_adjustment > 0:
        learning_status = "SUPPORT"
    elif learning_adjustment < 0:
        learning_status = "OPPOSE"
    elif (
        int(
            _safe_float(
                self_learning.get(
                    "symbol_evidence",
                    {},
                ).get("sample_size"),
                0.0,
            )
        )
        < 10
    ):
        learning_status = "INSUFFICIENT_SAMPLE"
    else:
        learning_status = "NEUTRAL"

    try:
        dashboard = build_self_learning_dashboard()
    except Exception as error:
        dashboard = {
            "status": "error",
            "version": "self_learning_v2",
            "reason": (
                "Self-learning dashboard could not be generated"
            ),
            "error": str(error),
            "overall": {
                "trade_count": 0,
            },
            "by_symbol": {},
            "by_strategy": {},
            "by_regime": {},
            "by_session": {},
        }

    return {
        "status": "success",
        "version": "runner_learning_diagnostics_v1",
        "diagnostics_only": True,
        "pattern_memory": pattern_memory,
        "self_learning": self_learning,
        "learning_dashboard": dashboard,
        "learning_adjustment": round(
            learning_adjustment,
            2,
        ),
        "pattern_adjustment": round(
            pattern_adjustment,
            2,
        ),
        "learning_status": learning_status,
        "selected_symbol": (
            candidate.get("symbol")
            or result.get("symbol")
        ),
        "execution_submitted": bool(
            _mapping(
                result.get("execution")
            ).get("submitted", False)
        ),
    }
