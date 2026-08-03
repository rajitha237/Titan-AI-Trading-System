"""Bounded multi-dimensional confidence calibration."""
from __future__ import annotations
from typing import Any

MAX_TOTAL_LEARNING_ADJUSTMENT = 5.0

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return default
        return number
    except (TypeError, ValueError):
        return default

def calibrate_learning_confidence(
    *,
    base_score: float,
    symbol_evidence: dict,
    strategy_evidence: dict,
    regime_evidence: dict,
    session_evidence: dict,
    pattern_memory: dict | None = None,
) -> dict:
    pattern_memory = pattern_memory if isinstance(pattern_memory, dict) else {}
    components = {
        "symbol": _safe_float(symbol_evidence.get("adjustment")),
        "strategy": _safe_float(strategy_evidence.get("adjustment")),
        "regime": _safe_float(regime_evidence.get("adjustment")),
        "session": _safe_float(session_evidence.get("adjustment")),
        "pattern_memory": _safe_float(pattern_memory.get("confidence_adjustment")),
    }
    weighted_raw = (
        components["symbol"] * 0.25
        + components["strategy"] * 0.25
        + components["regime"] * 0.25
        + components["session"] * 0.15
        + components["pattern_memory"] * 0.10
    )
    adjustment = max(-MAX_TOTAL_LEARNING_ADJUSTMENT, min(MAX_TOTAL_LEARNING_ADJUSTMENT, weighted_raw))
    calibrated = max(0.0, min(100.0, _safe_float(base_score) + adjustment))
    return {
        "status": "success",
        "version": "self_learning_v2",
        "base_score": round(_safe_float(base_score), 2),
        "raw_learning_adjustment": round(weighted_raw, 4),
        "learning_adjustment": round(adjustment, 2),
        "calibrated_score": round(calibrated, 2),
        "components": {key: round(value, 2) for key, value in components.items()},
        "maximum_total_adjustment": MAX_TOTAL_LEARNING_ADJUSTMENT,
        "advisory_only": True,
    }
