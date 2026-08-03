"""
TitanAI Trade Quality Gate v5

Direction-aware quality scoring with backward compatibility.

Features:
- Supports BUY and SELL setups
- Supports multiple confidence output key names
- Validates order-book and order-flow direction
- Uses liquidity trend as a directional confirmation
- Returns clear reasons and warnings
- TRADE / SMALL_TRADE / WATCH / REJECT actions
"""

from typing import Any


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)

        if result != result:
            return default

        if result in [
            float("inf"),
            float("-inf"),
        ]:
            return default

        return result

    except (TypeError, ValueError):
        return default


def _get_confidence_score(
    confidence: dict | None,
) -> float:
    """
    Read confidence score from common TitanAI formats.

    Supported keys:
    - confidence
    - confidence_score
    - score
    - final_confidence
    """
    confidence = confidence or {}

    for key in (
        "adjusted_confidence_score",
        "directional_confidence_score",
        "final_confidence",
        "confidence",
        "confidence_score",
        "score",
    ):
        if key in confidence:
            return _safe_float(
                confidence.get(key),
                0.0,
            )

    return 0.0


def _get_trade_direction(
    confidence: dict | None,
    validation: dict | None,
) -> str:
    """
    Resolve BUY or SELL direction from available engine outputs.
    """
    confidence = confidence or {}
    validation = validation or {}

    candidates = [
        confidence.get("signal"),
        confidence.get("raw_signal"),
        confidence.get("side"),
        confidence.get("direction"),
        validation.get("decision"),
        validation.get("signal"),
        validation.get("side"),
        validation.get("direction"),
    ]

    for candidate in candidates:
        direction = str(
            candidate or ""
        ).upper()

        if direction in [
            "BUY",
            "SELL",
        ]:
            return direction

    return "UNKNOWN"


def evaluate_trade_quality(
    order_book: dict,
    order_flow: dict,
    confidence: dict,
    validation: dict,
    liquidity_trend: dict | None = None,
    direction: str | None = None,
) -> dict:
    order_book = order_book or {}
    order_flow = order_flow or {}
    confidence = confidence or {}
    validation = validation or {}
    liquidity_trend = liquidity_trend or {}

    checks = []
    warnings = []
    score = 50

    provided_direction = str(
        direction or ""
    ).upper()

    if provided_direction in ["BUY", "SELL"]:
        direction = provided_direction
    else:
        direction = _get_trade_direction(
            confidence=confidence,
            validation=validation,
        )

    if direction == "UNKNOWN":
        warnings.append(
            "Trade direction could not be resolved"
        )

    # -------------------------------------------------
    # Validation
    # -------------------------------------------------

    validation_allowed = (
        validation.get("allowed") is True
    )

    if validation_allowed:
        score += 15
        checks.append({
            "name": "validation",
            "passed": True,
        })
    else:
        score -= 30
        checks.append({
            "name": "validation",
            "passed": False,
            "reason": validation.get("reason"),
        })

    # -------------------------------------------------
    # Confidence
    # -------------------------------------------------

    conf = _get_confidence_score(
        confidence
    )

    if conf >= 90:
        score += 15
        checks.append({
            "name": "confidence",
            "passed": True,
            "value": conf,
            "level": "strong",
        })

    elif conf >= 80:
        score += 5
        checks.append({
            "name": "confidence",
            "passed": True,
            "value": conf,
            "level": "watch",
        })

    else:
        score -= 20
        checks.append({
            "name": "confidence",
            "passed": False,
            "value": conf,
        })

    # -------------------------------------------------
    # Order-book pressure
    # -------------------------------------------------

    pressure = str(
        order_book.get("pressure") or "UNKNOWN"
    ).upper()

    imbalance = _safe_float(
        order_book.get("imbalance"),
        0.0,
    )

    expected_book_pressure = (
        "BUY_PRESSURE"
        if direction == "BUY"
        else "SELL_PRESSURE"
        if direction == "SELL"
        else None
    )

    opposite_book_pressure = (
        "SELL_PRESSURE"
        if direction == "BUY"
        else "BUY_PRESSURE"
        if direction == "SELL"
        else None
    )

    if (
        expected_book_pressure
        and pressure == expected_book_pressure
    ):
        score += 10
        checks.append({
            "name": "order_book_pressure",
            "passed": True,
            "pressure": pressure,
            "direction": direction,
        })

    elif pressure == "NEUTRAL":
        score += 3
        checks.append({
            "name": "order_book_pressure",
            "passed": True,
            "pressure": pressure,
            "direction": direction,
            "level": "neutral",
        })

    elif (
        opposite_book_pressure
        and pressure == opposite_book_pressure
    ):
        score -= 12
        checks.append({
            "name": "order_book_pressure",
            "passed": False,
            "pressure": pressure,
            "direction": direction,
            "reason": (
                "Order-book pressure opposes "
                "the trade direction"
            ),
        })

    else:
        checks.append({
            "name": "order_book_pressure",
            "passed": False,
            "pressure": pressure,
            "direction": direction,
            "reason": (
                "Order-book pressure is unavailable "
                "or unrecognized"
            ),
        })

    # -------------------------------------------------
    # Directional order-book imbalance
    # -------------------------------------------------

    directional_imbalance = (
        imbalance
        if direction != "SELL"
        else -imbalance
    )

    if directional_imbalance >= 0.15:
        score += 8
        checks.append({
            "name": "order_book_imbalance",
            "passed": True,
            "value": imbalance,
            "directional_value": (
                directional_imbalance
            ),
        })

    elif directional_imbalance >= -0.15:
        score += 2
        checks.append({
            "name": "order_book_imbalance",
            "passed": True,
            "value": imbalance,
            "directional_value": (
                directional_imbalance
            ),
            "level": "neutral",
        })

    else:
        score -= 10
        checks.append({
            "name": "order_book_imbalance",
            "passed": False,
            "value": imbalance,
            "directional_value": (
                directional_imbalance
            ),
            "reason": (
                "Order-book imbalance opposes "
                "the trade direction"
            ),
        })

    # -------------------------------------------------
    # Order flow
    # -------------------------------------------------

    flow_pressure = str(
        order_flow.get("pressure") or "UNKNOWN"
    ).upper()

    delta_ratio = _safe_float(
        order_flow.get("delta_ratio"),
        0.0,
    )

    whale_trades = (
        order_flow.get("whale_trades") or []
    )

    whale_buy_count = len([
        trade
        for trade in whale_trades
        if str(
            trade.get("side") or ""
        ).upper() == "BUY"
    ])

    whale_sell_count = len([
        trade
        for trade in whale_trades
        if str(
            trade.get("side") or ""
        ).upper() == "SELL"
    ])

    expected_flow_pressure = (
        "AGGRESSIVE_BUYERS"
        if direction == "BUY"
        else "AGGRESSIVE_SELLERS"
        if direction == "SELL"
        else None
    )

    opposite_flow_pressure = (
        "AGGRESSIVE_SELLERS"
        if direction == "BUY"
        else "AGGRESSIVE_BUYERS"
        if direction == "SELL"
        else None
    )

    if (
        expected_flow_pressure
        and flow_pressure == expected_flow_pressure
    ):
        score += 15
        checks.append({
            "name": "order_flow",
            "passed": True,
            "pressure": flow_pressure,
            "delta_ratio": delta_ratio,
            "direction": direction,
        })

    elif flow_pressure == "BALANCED":
        score += 3
        checks.append({
            "name": "order_flow",
            "passed": True,
            "pressure": flow_pressure,
            "delta_ratio": delta_ratio,
            "direction": direction,
            "level": "neutral",
        })

    elif (
        opposite_flow_pressure
        and flow_pressure == opposite_flow_pressure
    ):
        score -= 15
        checks.append({
            "name": "order_flow",
            "passed": False,
            "pressure": flow_pressure,
            "delta_ratio": delta_ratio,
            "direction": direction,
            "reason": (
                "Order flow opposes "
                "the trade direction"
            ),
        })

    else:
        checks.append({
            "name": "order_flow",
            "passed": False,
            "pressure": flow_pressure,
            "delta_ratio": delta_ratio,
            "direction": direction,
            "reason": (
                "Order-flow pressure is unavailable "
                "or unrecognized"
            ),
        })

    # -------------------------------------------------
    # Whale activity
    # -------------------------------------------------

    directional_whale_count = (
        whale_buy_count
        if direction == "BUY"
        else whale_sell_count
        if direction == "SELL"
        else 0
    )

    opposite_whale_count = (
        whale_sell_count
        if direction == "BUY"
        else whale_buy_count
        if direction == "SELL"
        else 0
    )

    if directional_whale_count > opposite_whale_count:
        score += 7
        checks.append({
            "name": "whale_activity",
            "passed": True,
            "buy_count": whale_buy_count,
            "sell_count": whale_sell_count,
            "direction": direction,
        })

    elif opposite_whale_count > directional_whale_count:
        score -= 7
        checks.append({
            "name": "whale_activity",
            "passed": False,
            "buy_count": whale_buy_count,
            "sell_count": whale_sell_count,
            "direction": direction,
            "reason": (
                "Whale activity opposes "
                "the trade direction"
            ),
        })

    else:
        checks.append({
            "name": "whale_activity",
            "passed": True,
            "buy_count": whale_buy_count,
            "sell_count": whale_sell_count,
            "direction": direction,
            "level": "neutral",
        })

    # -------------------------------------------------
    # Liquidity trend
    # -------------------------------------------------

    liq_signal = str(
        liquidity_trend.get("signal") or "NEUTRAL"
    ).upper()

    bullish_liquidity = {
        "BID_ACCUMULATION",
        "BID_SUPPORT",
        "ASK_WALL_REMOVED",
    }

    bearish_liquidity = {
        "ASK_DISTRIBUTION",
        "ASK_RESISTANCE",
        "BID_WALL_REMOVED",
    }

    liquidity_supports_direction = (
        direction == "BUY"
        and liq_signal in bullish_liquidity
    ) or (
        direction == "SELL"
        and liq_signal in bearish_liquidity
    )

    liquidity_opposes_direction = (
        direction == "BUY"
        and liq_signal in bearish_liquidity
    ) or (
        direction == "SELL"
        and liq_signal in bullish_liquidity
    )

    if liquidity_supports_direction:
        score += 8
        checks.append({
            "name": "liquidity_trend",
            "passed": True,
            "signal": liq_signal,
            "direction": direction,
        })

    elif liquidity_opposes_direction:
        score -= 8
        checks.append({
            "name": "liquidity_trend",
            "passed": False,
            "signal": liq_signal,
            "direction": direction,
            "reason": (
                "Liquidity trend opposes "
                "the trade direction"
            ),
        })

    else:
        checks.append({
            "name": "liquidity_trend",
            "passed": True,
            "signal": liq_signal,
            "direction": direction,
            "level": "neutral",
        })

    # -------------------------------------------------
    # Final quality decision
    # -------------------------------------------------

    score = max(
        0,
        min(100, score),
    )

    flow_is_opposite = (
        opposite_flow_pressure is not None
        and flow_pressure == opposite_flow_pressure
    )

    passed = (
        validation_allowed
        and direction in ["BUY", "SELL"]
        and conf >= 80
        and score >= 80
        and not flow_is_opposite
    )

    if not passed:
        if not validation_allowed:
            action = "REJECT"
        elif direction == "UNKNOWN":
            action = "REJECT"
        elif conf < 80:
            action = "REJECT"
        elif flow_is_opposite:
            action = "REJECT"
        elif score >= 70:
            action = "WATCH"
        else:
            action = "REJECT"

    elif score >= 90:
        action = "TRADE"

    else:
        action = "SMALL_TRADE"

    reasons = []

    if passed:
        reasons.append(
            "Trade quality requirements passed"
        )
    else:
        reasons.append(
            "Trade quality requirements did not pass"
        )

    return {
        "status": (
            "ready"
            if passed
            else "blocked"
        ),
        "passed": passed,
        "quality_score": round(
            score,
            2,
        ),
        "action": action,
        "direction": direction,
        "confidence_score": round(
            conf,
            2,
        ),
        "validation_allowed": (
            validation_allowed
        ),
        "flow_pressure": flow_pressure,
        "order_book_pressure": pressure,
        "reasons": reasons,
        "warnings": warnings,
        "checks": checks,
        "primary_blockers": [
            check.get("reason")
            or check.get("name")
            for check in checks
            if check.get("passed") is False
        ],
        "thresholds": {
            "minimum_confidence": 80.0,
            "minimum_quality_score": 80.0,
        },
    }