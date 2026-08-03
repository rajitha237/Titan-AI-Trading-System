"""TitanAI Dynamic Position Sizer v26."""

from __future__ import annotations

from typing import Any


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)
        if result != result:
            return default
        if result in {
            float("inf"),
            float("-inf"),
        }:
            return default
        return result
    except (TypeError, ValueError):
        return default


def calculate_dynamic_position_size(
    *,
    balance: float,
    base_risk_percent: float = 1.0,
    stop_loss_percent: float = 1.0,
    confidence_score: float = 75.0,
    volatility_percent: float = 1.0,
    requested_leverage: float = 5.0,
    maximum_leverage: float = 5.0,
    maximum_position_percent: float = 25.0,
    minimum_position_usdt: float = 5.0,
) -> dict:
    """Return a bounded advisory position-size recommendation."""
    balance = max(0.0, _safe_float(balance))
    base_risk_percent = max(
        0.1,
        min(2.0, _safe_float(base_risk_percent, 1.0)),
    )
    stop_loss_percent = max(
        0.01,
        _safe_float(stop_loss_percent, 1.0),
    )
    confidence_score = max(
        0.0,
        min(100.0, _safe_float(confidence_score)),
    )
    volatility_percent = max(
        0.01,
        _safe_float(volatility_percent, 1.0),
    )
    leverage = max(
        1.0,
        min(
            _safe_float(requested_leverage, 1.0),
            max(1.0, _safe_float(maximum_leverage, 5.0)),
        ),
    )
    max_position_percent = max(
        1.0,
        min(
            100.0,
            _safe_float(maximum_position_percent, 25.0),
        ),
    )

    confidence_multiplier = (
        0.50
        if confidence_score < 70
        else 0.75
        if confidence_score < 80
        else 1.00
        if confidence_score < 90
        else 1.10
    )

    volatility_multiplier = max(
        0.50,
        min(
            1.00,
            1.0 / max(volatility_percent, 1.0),
        ),
    )

    effective_risk_percent = (
        base_risk_percent
        * confidence_multiplier
        * volatility_multiplier
    )

    risk_amount = (
        balance
        * effective_risk_percent
        / 100.0
    )

    raw_position_size = (
        risk_amount
        / (stop_loss_percent / 100.0)
    )

    exposure_cap = (
        balance
        * max_position_percent
        / 100.0
    )

    leverage_cap = balance * leverage

    recommended_position_usdt = min(
        raw_position_size,
        exposure_cap,
        leverage_cap,
    )

    margin_required = (
        recommended_position_usdt / leverage
        if leverage > 0
        else 0.0
    )

    executable = (
        balance > 0
        and recommended_position_usdt
        >= max(0.0, minimum_position_usdt)
    )

    block_reasons = []

    if balance <= 0:
        block_reasons.append(
            "Balance must be greater than zero"
        )

    if recommended_position_usdt < minimum_position_usdt:
        block_reasons.append(
            "Recommended position is below exchange minimum notional"
        )

    return {
        "status": "ready",
        "version": "v26",
        "executable": executable,
        "balance": round(balance, 8),
        "base_risk_percent": round(
            base_risk_percent,
            4,
        ),
        "effective_risk_percent": round(
            effective_risk_percent,
            4,
        ),
        "risk_amount": round(risk_amount, 8),
        "confidence_score": round(
            confidence_score,
            2,
        ),
        "confidence_multiplier": round(
            confidence_multiplier,
            4,
        ),
        "volatility_percent": round(
            volatility_percent,
            4,
        ),
        "volatility_multiplier": round(
            volatility_multiplier,
            4,
        ),
        "recommended_leverage": round(
            leverage,
            4,
        ),
        "recommended_position_usdt": round(
            recommended_position_usdt,
            8,
        ),
        "margin_required": round(
            margin_required,
            8,
        ),
        "maximum_position_usdt": round(
            exposure_cap,
            8,
        ),
        "block_reasons": block_reasons,
        "advisory_only": True,
    }
