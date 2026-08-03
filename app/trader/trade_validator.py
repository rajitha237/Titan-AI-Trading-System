"""
TitanAI Trade Validator v3

Validates a directional AI trade setup before it reaches the Trade Quality,
Risk Engine, Trade Builder, and execution layers.

Main improvements over v2:
- Keeps the existing validate_trade(...) function signature.
- Uses directional BUY/SELL score thresholds.
- Preserves strict order-book and multi-timeframe validation.
- Supports a tightly controlled MACD override for exceptionally strong setups.
- Produces a detailed audit trail for journaling and later analysis.
- Never places orders and never bypasses downstream risk controls.
"""

from __future__ import annotations

from math import isfinite
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple


BUY_SCORE_THRESHOLD = 75.0
SELL_SCORE_THRESHOLD = 35.0
VALID_DECISIONS = {"BUY", "SELL"}

# A MACD conflict can only be overridden when the directional AI score is
# exceptionally strong and enough independent confirmations agree.
BUY_MACD_OVERRIDE_SCORE = 95.0
SELL_MACD_OVERRIDE_SCORE = 5.0
MIN_OVERRIDE_CONFIRMATIONS = 4


BULLISH_VALUES = {
    "BUY",
    "BULLISH",
    "STRONG_BUY",
    "BUY_PRESSURE",
    "ACCUMULATION",
    "ABOVE_VWAP",
    "LONG",
}

BEARISH_VALUES = {
    "SELL",
    "BEARISH",
    "STRONG_SELL",
    "SELL_PRESSURE",
    "DISTRIBUTION",
    "BELOW_VWAP",
    "SHORT",
}


Check = Dict[str, Any]
ValidationResult = Dict[str, Any]


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to a finite float without raising an exception."""
    try:
        result = float(value)
        return result if isfinite(result) else default
    except (TypeError, ValueError):
        return default


def _normalise_text(value: Any) -> str:
    """Return a stripped uppercase representation of a value."""
    return str(value or "").strip().upper()


def _first_value(mapping: Mapping[str, Any], keys: Iterable[str]) -> Any:
    """Return the first present, non-empty value from a mapping."""
    for key in keys:
        if key not in mapping:
            continue

        value = mapping.get(key)
        if value is not None and value != "":
            return value

    return None


def _nested_mapping(mapping: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    """Safely return a nested mapping."""
    value = mapping.get(key)
    return value if isinstance(value, Mapping) else {}


def _add_check(
    checks: List[Check],
    *,
    name: str,
    passed: bool,
    value: Any = None,
    required: Any = None,
    status: Optional[str] = None,
    details: Optional[str] = None,
) -> None:
    """Append a consistent validation check record."""
    check: Check = {
        "name": name,
        "passed": bool(passed),
        "value": value,
    }

    if required is not None:
        check["required"] = required
    if status:
        check["status"] = status
    if details:
        check["details"] = details

    checks.append(check)


def _summary(checks: List[Check]) -> Dict[str, int]:
    """Return compact check statistics."""
    passed = sum(1 for check in checks if check.get("passed") is True)
    failed = sum(1 for check in checks if check.get("passed") is False)
    warnings = sum(1 for check in checks if check.get("status") == "WARNING")

    return {
        "total": len(checks),
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
    }


def _result(
    *,
    allowed: bool,
    reason: str,
    decision: str,
    score: float,
    ai_signal: str,
    checks: List[Check],
    warning: Optional[str] = None,
    override_used: bool = False,
    override_checks: Optional[Dict[str, Any]] = None,
) -> ValidationResult:
    """Create a consistent validator response."""
    payload: ValidationResult = {
        "allowed": bool(allowed),
        "reason": reason,
        "decision": decision,
        "score": score,
        "ai_signal": ai_signal,
        "warning": warning,
        "override_used": bool(override_used),
        "override_checks": override_checks or {},
        "checks": checks,
        "summary": _summary(checks),
        "validator_version": "3.0",
    }

    return payload


def _direction_matches(decision: str, value: Any) -> Optional[bool]:
    """
    Interpret a directional value.

    Returns:
        True: value supports the decision.
        False: value opposes the decision.
        None: value is absent or neutral/unknown.
    """
    normalised = _normalise_text(value)

    if not normalised or normalised in {"NEUTRAL", "MIXED", "NONE", "UNKNOWN", "N/A"}:
        return None

    if normalised in BULLISH_VALUES:
        return decision == "BUY"

    if normalised in BEARISH_VALUES:
        return decision == "SELL"

    return None


def _extract_confirmation_score(
    final_decision: Mapping[str, Any],
    ai_score: Mapping[str, Any],
) -> Optional[float]:
    """Find an optional confirmation score without changing the public API."""
    candidates = [
        _first_value(final_decision, ("confirmation_score", "confidence_score")),
        _first_value(ai_score, ("confirmation_score", "confidence_score")),
        _first_value(_nested_mapping(final_decision, "confirmation"), ("score", "confidence")),
        _first_value(_nested_mapping(ai_score, "confirmation"), ("score", "confidence")),
    ]

    for candidate in candidates:
        if candidate is not None:
            return _safe_float(candidate, default=0.0)

    return None


def _collect_override_confirmations(
    *,
    decision: str,
    final_decision: Mapping[str, Any],
    ai_score: Mapping[str, Any],
    order_book: Mapping[str, Any],
    technical: Mapping[str, Any],
    multi_timeframe: Mapping[str, Any],
) -> Tuple[Dict[str, Any], int, int]:
    """
    Collect independent directional evidence for a possible MACD override.

    Only fields already present in the supplied dictionaries are evaluated.
    Missing or neutral fields do not count as either passed or failed.
    """
    feature_sources: Dict[str, Any] = {
        "multi_timeframe": _first_value(
            multi_timeframe,
            ("overall_trend", "trend", "direction", "signal"),
        ),
        "order_book": _first_value(
            order_book,
            ("pressure", "direction", "signal", "dominance"),
        ),
        "market_structure": _first_value(
            technical,
            ("market_structure", "structure", "structure_direction"),
        ),
        "ema_trend": _first_value(
            technical,
            ("trend", "ema_trend"),
        ),
        "vwap": _first_value(
            technical,
            ("vwap_signal", "vwap_direction", "vwap_trend", "vwap_position"),
        ),
        "whales": _first_value(
            final_decision,
            ("whale_state", "whale_signal", "whale_activity"),
        )
        or _first_value(
            ai_score,
            ("whale_state", "whale_signal", "whale_activity"),
        ),
        "liquidity": _first_value(
            final_decision,
            ("liquidity_signal", "liquidity_direction", "liquidity"),
        )
        or _first_value(
            ai_score,
            ("liquidity_signal", "liquidity_direction", "liquidity"),
        ),
        "fvg": _first_value(
            technical,
            ("fvg_signal", "fvg_direction", "fair_value_gap"),
        ),
    }

    confirmation_score = _extract_confirmation_score(final_decision, ai_score)
    audit: Dict[str, Any] = {}
    passed = 0
    failed = 0

    if confirmation_score is not None:
        score_passed = confirmation_score >= 90.0
        audit["confirmation_score"] = {
            "available": True,
            "passed": score_passed,
            "value": confirmation_score,
            "required": ">= 90",
        }
        if score_passed:
            passed += 1
        else:
            failed += 1
    else:
        audit["confirmation_score"] = {
            "available": False,
            "passed": None,
            "value": None,
            "required": ">= 90 when supplied",
        }

    for name, value in feature_sources.items():
        directional_match = _direction_matches(decision, value)
        audit[name] = {
            "available": directional_match is not None,
            "passed": directional_match,
            "value": _normalise_text(value) if value is not None else None,
        }

        if directional_match is True:
            passed += 1
        elif directional_match is False:
            failed += 1

    return audit, passed, failed


def _macd_override_allowed(
    *,
    decision: str,
    score: float,
    final_decision: Mapping[str, Any],
    ai_score: Mapping[str, Any],
    order_book: Mapping[str, Any],
    technical: Mapping[str, Any],
    multi_timeframe: Mapping[str, Any],
) -> Tuple[bool, Dict[str, Any], str]:
    """Evaluate the tightly controlled adaptive MACD override."""
    score_passed = (
        score >= BUY_MACD_OVERRIDE_SCORE
        if decision == "BUY"
        else score <= SELL_MACD_OVERRIDE_SCORE
    )

    audit, passed_confirmations, failed_confirmations = _collect_override_confirmations(
        decision=decision,
        final_decision=final_decision,
        ai_score=ai_score,
        order_book=order_book,
        technical=technical,
        multi_timeframe=multi_timeframe,
    )

    audit["directional_ai_score"] = {
        "available": True,
        "passed": score_passed,
        "value": score,
        "required": (
            f">= {BUY_MACD_OVERRIDE_SCORE:g}"
            if decision == "BUY"
            else f"<= {SELL_MACD_OVERRIDE_SCORE:g}"
        ),
    }
    audit["confirmation_totals"] = {
        "passed": passed_confirmations,
        "failed": failed_confirmations,
        "required_passed": MIN_OVERRIDE_CONFIRMATIONS,
        "required_failed": 0,
    }

    allowed = (
        score_passed
        and passed_confirmations >= MIN_OVERRIDE_CONFIRMATIONS
        and failed_confirmations == 0
    )

    if not score_passed:
        reason = "Directional AI score is not strong enough for MACD override"
    elif failed_confirmations > 0:
        reason = "One or more independent confirmations oppose the trade"
    elif passed_confirmations < MIN_OVERRIDE_CONFIRMATIONS:
        reason = (
            "Not enough independent confirmations for MACD override "
            f"({passed_confirmations}/{MIN_OVERRIDE_CONFIRMATIONS})"
        )
    else:
        reason = "High-confidence multi-factor MACD override approved"

    return allowed, audit, reason


def validate_trade(
    final_decision: dict,
    ai_score: dict,
    order_book: dict,
    technical: dict,
    multi_timeframe: dict,
) -> dict:
    """
    Validate a BUY or SELL setup using directional score thresholds and
    independent market confirmations.

    The function keeps the v2 public signature for drop-in compatibility.
    It does not place orders and does not override Trade Quality, Risk Engine,
    account-protection, exchange-filter, or execution-layer checks.
    """
    final_decision = final_decision or {}
    ai_score = ai_score or {}
    order_book = order_book or {}
    technical = technical or {}
    multi_timeframe = multi_timeframe or {}

    decision = _normalise_text(
        final_decision.get(
            "decision",
            final_decision.get("signal", "HOLD"),
        )
    )
    score = _safe_float(ai_score.get("score"), 50.0)
    ai_signal = _normalise_text(ai_score.get("signal", "HOLD"))
    order_book_pressure = _normalise_text(
        order_book.get("pressure", "NEUTRAL")
    )
    mtf_trend = _normalise_text(
        multi_timeframe.get("overall_trend", "MIXED")
    )
    macd_direction = _normalise_text(
        technical.get("macd_direction", "NEUTRAL")
    )

    checks: List[Check] = []

    if decision not in VALID_DECISIONS:
        _add_check(
            checks,
            name="decision",
            passed=False,
            value=decision,
            required="BUY or SELL",
        )
        return _result(
            allowed=False,
            reason="Decision is HOLD or invalid",
            decision=decision,
            score=score,
            ai_signal=ai_signal,
            checks=checks,
        )

    _add_check(checks, name="decision", passed=True, value=decision)

    if ai_signal in VALID_DECISIONS and ai_signal != decision:
        _add_check(
            checks,
            name="ai_signal_alignment",
            passed=False,
            value=ai_signal,
            required=decision,
        )
        return _result(
            allowed=False,
            reason=f"Final decision {decision} conflicts with AI signal {ai_signal}",
            decision=decision,
            score=score,
            ai_signal=ai_signal,
            checks=checks,
        )

    _add_check(
        checks,
        name="ai_signal_alignment",
        passed=True,
        value=ai_signal,
        required=decision,
    )

    score_allowed = (
        score >= BUY_SCORE_THRESHOLD
        if decision == "BUY"
        else score <= SELL_SCORE_THRESHOLD
    )
    _add_check(
        checks,
        name="directional_ai_score",
        passed=score_allowed,
        value=score,
        required=(
            f">= {BUY_SCORE_THRESHOLD:g}"
            if decision == "BUY"
            else f"<= {SELL_SCORE_THRESHOLD:g}"
        ),
    )

    if not score_allowed:
        reason = (
            f"BUY AI score below {BUY_SCORE_THRESHOLD:g}"
            if decision == "BUY"
            else f"SELL AI score above {SELL_SCORE_THRESHOLD:g}"
        )
        return _result(
            allowed=False,
            reason=reason,
            decision=decision,
            score=score,
            ai_signal=ai_signal,
            checks=checks,
        )

    order_book_conflict = (
        decision == "BUY" and order_book_pressure == "SELL_PRESSURE"
    ) or (
        decision == "SELL" and order_book_pressure == "BUY_PRESSURE"
    )
    _add_check(
        checks,
        name="order_book",
        passed=not order_book_conflict,
        value=order_book_pressure,
        required=f"not opposite to {decision}",
    )

    if order_book_conflict:
        return _result(
            allowed=False,
            reason=f"Order book conflicts with {decision}",
            decision=decision,
            score=score,
            ai_signal=ai_signal,
            checks=checks,
        )

    required_mtf = "BULLISH" if decision == "BUY" else "BEARISH"
    mtf_allowed = mtf_trend == required_mtf
    _add_check(
        checks,
        name="multi_timeframe",
        passed=mtf_allowed,
        value=mtf_trend,
        required=required_mtf,
    )

    if not mtf_allowed:
        return _result(
            allowed=False,
            reason=f"Multi-timeframe trend not {required_mtf.lower()}",
            decision=decision,
            score=score,
            ai_signal=ai_signal,
            checks=checks,
        )

    macd_confirmed = macd_direction == decision

    if macd_confirmed:
        _add_check(
            checks,
            name="macd",
            passed=True,
            value=macd_direction,
            required=decision,
        )
        return _result(
            allowed=True,
            reason="All validation rules passed",
            decision=decision,
            score=score,
            ai_signal=ai_signal,
            checks=checks,
        )

    override_allowed, override_checks, override_reason = _macd_override_allowed(
        decision=decision,
        score=score,
        final_decision=final_decision,
        ai_score=ai_score,
        order_book=order_book,
        technical=technical,
        multi_timeframe=multi_timeframe,
    )

    if not override_allowed:
        _add_check(
            checks,
            name="macd",
            passed=False,
            value=macd_direction,
            required=decision,
            details=override_reason,
        )
        return _result(
            allowed=False,
            reason=f"MACD does not confirm {decision}: {override_reason}",
            decision=decision,
            score=score,
            ai_signal=ai_signal,
            checks=checks,
            override_checks=override_checks,
        )

    warning = (
        f"MACD currently indicates {macd_direction or 'NEUTRAL'}, but a "
        "high-confidence multi-factor override was applied"
    )
    _add_check(
        checks,
        name="macd",
        passed=True,
        value=macd_direction,
        required=decision,
        status="WARNING",
        details="Adaptive MACD override applied",
    )

    return _result(
        allowed=True,
        reason="High-confidence setup approved with MACD override",
        decision=decision,
        score=score,
        ai_signal=ai_signal,
        checks=checks,
        warning=warning,
        override_used=True,
        override_checks=override_checks,
    )