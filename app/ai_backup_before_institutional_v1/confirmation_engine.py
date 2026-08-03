"""
TitanAI Confirmation Engine v1

Validates the raw AI signal using independent confirmation layers.

Confirmation sources:
- Order Flow
- Liquidity Trend
- Liquidity Sweep
- Absorption
- Iceberg Liquidity
- Whale Activity
- Market Structure
- Volume Profile
- VWAP
- Fair Value Gaps
- Technical Trend
- Multi-Timeframe Trend

Output decisions:
- APPROVE
- WATCH
- REJECT
"""

from typing import Any


APPROVE_THRESHOLD = 75
WATCH_THRESHOLD = 55

MIN_WHALE_SAMPLES = 5
STRONG_SIGNAL_THRESHOLD = 70


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _add_check(
    checks: list,
    name: str,
    passed: bool,
    impact: int,
    value: Any = None,
    reason: str | None = None,
) -> None:
    check = {
        "name": name,
        "passed": passed,
        "impact": impact,
    }

    if value is not None:
        check["value"] = value

    if reason:
        check["reason"] = reason

    checks.append(check)


def evaluate_trade_confirmation(
    ai_score: dict | None,
    order_flow: dict | None,
    liquidity_trend: dict | None,
    liquidity_sweep: dict | None,
    absorption: dict | None,
    iceberg: dict | None,
    whale_activity: dict | None,
    market_structure: dict | None,
    volume_profile: dict | None,
    vwap: dict | None,
    fair_value_gaps: dict | None,
    technical: dict | None,
    multi_timeframe: dict | None,
) -> dict:
    ai_score = ai_score or {}
    order_flow = order_flow or {}
    liquidity_trend = liquidity_trend or {}
    liquidity_sweep = liquidity_sweep or {}
    absorption = absorption or {}
    iceberg = iceberg or {}
    whale_activity = whale_activity or {}
    market_structure = market_structure or {}
    volume_profile = volume_profile or {}
    vwap = vwap or {}
    fair_value_gaps = fair_value_gaps or {}
    technical = technical or {}
    multi_timeframe = multi_timeframe or {}

    raw_score = int(
        max(
            0,
            min(
                100,
                _safe_float(
                    ai_score.get("score"),
                    0,
                ),
            ),
        )
    )

    raw_signal = ai_score.get(
        "signal",
        "HOLD",
    )

    checks = []
    hard_blocks = []
    warnings = []
    positive_confirmations = 0
    negative_confirmations = 0

    if raw_signal not in ["BUY", "SELL"]:
        return {
            "status": "ready",
            "passed": False,
            "decision": "REJECT",
            "raw_signal": raw_signal,
            "raw_score": raw_score,
            "confirmation_score": 0,
            "positive_confirmations": 0,
            "negative_confirmations": 0,
            "hard_blocks": [
                "Raw AI signal is HOLD or invalid"
            ],
            "warnings": [],
            "checks": [],
            "reasons": [
                "Trade confirmation rejected because the raw signal is not BUY or SELL"
            ],
        }

    confirmation_score = 50

    # ---------------------------------------------------------
    # Raw AI Score
    # ---------------------------------------------------------

    if raw_score >= 90:
        confirmation_score += 12
        positive_confirmations += 1

        _add_check(
            checks=checks,
            name="raw_ai_score",
            passed=True,
            impact=12,
            value=raw_score,
            reason="Raw AI score is very strong",
        )

    elif raw_score >= 75:
        confirmation_score += 7
        positive_confirmations += 1

        _add_check(
            checks=checks,
            name="raw_ai_score",
            passed=True,
            impact=7,
            value=raw_score,
            reason="Raw AI score passes the trade threshold",
        )

    else:
        confirmation_score -= 20
        negative_confirmations += 1
        hard_blocks.append(
            "Raw AI score is below the trade threshold"
        )

        _add_check(
            checks=checks,
            name="raw_ai_score",
            passed=False,
            impact=-20,
            value=raw_score,
            reason="Raw AI score is too low",
        )

    # ---------------------------------------------------------
    # Order Flow
    # ---------------------------------------------------------

    flow_pressure = order_flow.get("pressure")
    delta_ratio = _safe_float(
        order_flow.get("delta_ratio"),
        0,
    )

    if raw_signal == "BUY":
        if flow_pressure == "AGGRESSIVE_BUYERS":
            confirmation_score += 12
            positive_confirmations += 1

            _add_check(
                checks,
                "order_flow",
                True,
                12,
                flow_pressure,
                "Aggressive buyers confirm the BUY signal",
            )

        elif flow_pressure == "AGGRESSIVE_SELLERS":
            confirmation_score -= 25
            negative_confirmations += 1
            hard_blocks.append(
                "Aggressive sellers oppose the BUY signal"
            )

            _add_check(
                checks,
                "order_flow",
                False,
                -25,
                flow_pressure,
                "Aggressive sellers oppose the BUY signal",
            )

        else:
            confirmation_score += 2

            _add_check(
                checks,
                "order_flow",
                True,
                2,
                flow_pressure,
                "Balanced order flow does not strongly confirm the signal",
            )

        if delta_ratio <= -0.30:
            confirmation_score -= 8
            negative_confirmations += 1
            warnings.append(
                "Order-flow delta is strongly negative"
            )

    else:
        if flow_pressure == "AGGRESSIVE_SELLERS":
            confirmation_score += 12
            positive_confirmations += 1

            _add_check(
                checks,
                "order_flow",
                True,
                12,
                flow_pressure,
                "Aggressive sellers confirm the SELL signal",
            )

        elif flow_pressure == "AGGRESSIVE_BUYERS":
            confirmation_score -= 25
            negative_confirmations += 1
            hard_blocks.append(
                "Aggressive buyers oppose the SELL signal"
            )

            _add_check(
                checks,
                "order_flow",
                False,
                -25,
                flow_pressure,
                "Aggressive buyers oppose the SELL signal",
            )

        else:
            confirmation_score += 2

            _add_check(
                checks,
                "order_flow",
                True,
                2,
                flow_pressure,
                "Balanced order flow does not strongly confirm the signal",
            )

        if delta_ratio >= 0.30:
            confirmation_score -= 8
            negative_confirmations += 1
            warnings.append(
                "Order-flow delta is strongly positive"
            )

    # ---------------------------------------------------------
    # Market Structure
    # ---------------------------------------------------------

    structure = market_structure.get("structure")
    structure_signal = market_structure.get("signal")

    bullish_structure_signals = [
        "BULLISH_BOS",
        "BULLISH_CHOCH",
    ]

    bearish_structure_signals = [
        "BEARISH_BOS",
        "BEARISH_CHOCH",
    ]

    if raw_signal == "BUY":
        if structure_signal in bullish_structure_signals:
            confirmation_score += 14
            positive_confirmations += 1

            _add_check(
                checks,
                "market_structure",
                True,
                14,
                structure_signal,
                "Bullish structure break confirms the BUY signal",
            )

        elif structure_signal in bearish_structure_signals:
            confirmation_score -= 25
            negative_confirmations += 1
            hard_blocks.append(
                "Bearish market structure break opposes the BUY signal"
            )

            _add_check(
                checks,
                "market_structure",
                False,
                -25,
                structure_signal,
                "Bearish structure break opposes the BUY signal",
            )

        elif structure == "BULLISH":
            confirmation_score += 8
            positive_confirmations += 1

            _add_check(
                checks,
                "market_structure",
                True,
                8,
                structure,
                "Bullish market structure supports the BUY signal",
            )

        elif structure == "BEARISH":
            confirmation_score -= 10
            negative_confirmations += 1

            _add_check(
                checks,
                "market_structure",
                False,
                -10,
                structure,
                "Bearish market structure weakens the BUY signal",
            )

        else:
            warnings.append(
                "Market structure is mixed or unclear"
            )

    else:
        if structure_signal in bearish_structure_signals:
            confirmation_score += 14
            positive_confirmations += 1

            _add_check(
                checks,
                "market_structure",
                True,
                14,
                structure_signal,
                "Bearish structure break confirms the SELL signal",
            )

        elif structure_signal in bullish_structure_signals:
            confirmation_score -= 25
            negative_confirmations += 1
            hard_blocks.append(
                "Bullish market structure break opposes the SELL signal"
            )

            _add_check(
                checks,
                "market_structure",
                False,
                -25,
                structure_signal,
                "Bullish structure break opposes the SELL signal",
            )

        elif structure == "BEARISH":
            confirmation_score += 8
            positive_confirmations += 1

            _add_check(
                checks,
                "market_structure",
                True,
                8,
                structure,
                "Bearish market structure supports the SELL signal",
            )

        elif structure == "BULLISH":
            confirmation_score -= 10
            negative_confirmations += 1

            _add_check(
                checks,
                "market_structure",
                False,
                -10,
                structure,
                "Bullish market structure weakens the SELL signal",
            )

        else:
            warnings.append(
                "Market structure is mixed or unclear"
            )

    # ---------------------------------------------------------
    # VWAP
    # ---------------------------------------------------------

    vwap_bias = vwap.get("bias")
    vwap_trend = vwap.get("vwap_trend")
    mean_reversion_warning = bool(
        vwap.get("mean_reversion_warning")
    )
    mean_reversion_direction = vwap.get(
        "mean_reversion_direction"
    )

    if raw_signal == "BUY":
        if (
            vwap_bias == "ABOVE_VWAP"
            and vwap_trend == "RISING"
        ):
            confirmation_score += 8
            positive_confirmations += 1

            _add_check(
                checks,
                "vwap",
                True,
                8,
                {
                    "bias": vwap_bias,
                    "trend": vwap_trend,
                },
                "Price is above a rising VWAP",
            )

        elif (
            vwap_bias == "BELOW_VWAP"
            and vwap_trend == "FALLING"
        ):
            confirmation_score -= 18
            negative_confirmations += 1
            hard_blocks.append(
                "Price is below a falling VWAP"
            )

            _add_check(
                checks,
                "vwap",
                False,
                -18,
                {
                    "bias": vwap_bias,
                    "trend": vwap_trend,
                },
                "VWAP opposes the BUY signal",
            )

        if (
            mean_reversion_warning
            and mean_reversion_direction == "DOWN"
        ):
            confirmation_score -= 8
            negative_confirmations += 1
            warnings.append(
                "Price is overextended above VWAP"
            )

    else:
        if (
            vwap_bias == "BELOW_VWAP"
            and vwap_trend == "FALLING"
        ):
            confirmation_score += 8
            positive_confirmations += 1

            _add_check(
                checks,
                "vwap",
                True,
                8,
                {
                    "bias": vwap_bias,
                    "trend": vwap_trend,
                },
                "Price is below a falling VWAP",
            )

        elif (
            vwap_bias == "ABOVE_VWAP"
            and vwap_trend == "RISING"
        ):
            confirmation_score -= 18
            negative_confirmations += 1
            hard_blocks.append(
                "Price is above a rising VWAP"
            )

            _add_check(
                checks,
                "vwap",
                False,
                -18,
                {
                    "bias": vwap_bias,
                    "trend": vwap_trend,
                },
                "VWAP opposes the SELL signal",
            )

        if (
            mean_reversion_warning
            and mean_reversion_direction == "UP"
        ):
            confirmation_score -= 8
            negative_confirmations += 1
            warnings.append(
                "Price is overextended below VWAP"
            )

    # ---------------------------------------------------------
    # Volume Profile
    # ---------------------------------------------------------

    profile_bias = volume_profile.get("bias")
    profile_acceptance = volume_profile.get(
        "acceptance"
    )

    if raw_signal == "BUY":
        if (
            profile_bias == "ABOVE_VALUE"
            and profile_acceptance == "ABOVE_POC"
        ):
            confirmation_score += 7
            positive_confirmations += 1

            _add_check(
                checks,
                "volume_profile",
                True,
                7,
                profile_bias,
                "Price is accepted above the value area and POC",
            )

        elif (
            profile_bias == "BELOW_VALUE"
            and profile_acceptance == "BELOW_POC"
        ):
            confirmation_score -= 15
            negative_confirmations += 1
            hard_blocks.append(
                "Volume profile is bearish for a BUY trade"
            )

            _add_check(
                checks,
                "volume_profile",
                False,
                -15,
                profile_bias,
                "Price is accepted below value",
            )

    else:
        if (
            profile_bias == "BELOW_VALUE"
            and profile_acceptance == "BELOW_POC"
        ):
            confirmation_score += 7
            positive_confirmations += 1

            _add_check(
                checks,
                "volume_profile",
                True,
                7,
                profile_bias,
                "Price is accepted below the value area and POC",
            )

        elif (
            profile_bias == "ABOVE_VALUE"
            and profile_acceptance == "ABOVE_POC"
        ):
            confirmation_score -= 15
            negative_confirmations += 1
            hard_blocks.append(
                "Volume profile is bullish for a SELL trade"
            )

            _add_check(
                checks,
                "volume_profile",
                False,
                -15,
                profile_bias,
                "Price is accepted above value",
            )

    # ---------------------------------------------------------
    # Fair Value Gap
    # ---------------------------------------------------------

    fvg_signal = fair_value_gaps.get("signal")
    fvg_strength = _safe_float(
        fair_value_gaps.get("strength"),
        0,
    )

    if raw_signal == "BUY":
        if fvg_signal == "BULLISH_FVG_RETEST":
            confirmation_score += 10
            positive_confirmations += 1

            _add_check(
                checks,
                "fair_value_gap",
                True,
                10,
                fvg_signal,
                "Bullish FVG retest confirms the BUY signal",
            )

        elif fvg_signal == "BULLISH_FVG_NEARBY":
            confirmation_score += 4
            positive_confirmations += 1

            _add_check(
                checks,
                "fair_value_gap",
                True,
                4,
                fvg_signal,
                "Bullish FVG is nearby",
            )

        elif fvg_signal == "BEARISH_FVG_RETEST":
            confirmation_score -= 18
            negative_confirmations += 1

            if fvg_strength >= 80:
                hard_blocks.append(
                    "Strong bearish FVG retest opposes the BUY signal"
                )

            _add_check(
                checks,
                "fair_value_gap",
                False,
                -18,
                fvg_signal,
                "Bearish FVG retest opposes the BUY signal",
            )

        elif fvg_signal == "BEARISH_FVG_NEARBY":
            confirmation_score -= 6
            negative_confirmations += 1

            _add_check(
                checks,
                "fair_value_gap",
                False,
                -6,
                fvg_signal,
                "Bearish FVG is nearby",
            )

    else:
        if fvg_signal == "BEARISH_FVG_RETEST":
            confirmation_score += 10
            positive_confirmations += 1

            _add_check(
                checks,
                "fair_value_gap",
                True,
                10,
                fvg_signal,
                "Bearish FVG retest confirms the SELL signal",
            )

        elif fvg_signal == "BEARISH_FVG_NEARBY":
            confirmation_score += 4
            positive_confirmations += 1

            _add_check(
                checks,
                "fair_value_gap",
                True,
                4,
                fvg_signal,
                "Bearish FVG is nearby",
            )

        elif fvg_signal == "BULLISH_FVG_RETEST":
            confirmation_score -= 18
            negative_confirmations += 1

            if fvg_strength >= 80:
                hard_blocks.append(
                    "Strong bullish FVG retest opposes the SELL signal"
                )

            _add_check(
                checks,
                "fair_value_gap",
                False,
                -18,
                fvg_signal,
                "Bullish FVG retest opposes the SELL signal",
            )

        elif fvg_signal == "BULLISH_FVG_NEARBY":
            confirmation_score -= 6
            negative_confirmations += 1

            _add_check(
                checks,
                "fair_value_gap",
                False,
                -6,
                fvg_signal,
                "Bullish FVG is nearby",
            )

    # ---------------------------------------------------------
    # Whale Activity
    # ---------------------------------------------------------

    whale_state = whale_activity.get("state")
    whale_strength = _safe_float(
        whale_activity.get("strength"),
        0,
    )
    whale_samples = int(
        _safe_float(
            whale_activity.get("samples"),
            0,
        )
    )

    if whale_samples < MIN_WHALE_SAMPLES:
        warnings.append(
            "Whale engine does not yet have enough samples"
        )

    elif raw_signal == "BUY":
        if whale_state == "ACCUMULATION":
            impact = (
                8
                if whale_strength >= STRONG_SIGNAL_THRESHOLD
                else 4
            )

            confirmation_score += impact
            positive_confirmations += 1

            _add_check(
                checks,
                "whale_activity",
                True,
                impact,
                whale_state,
                "Whale accumulation supports the BUY signal",
            )

        elif whale_state == "DISTRIBUTION":
            impact = (
                -15
                if whale_strength >= STRONG_SIGNAL_THRESHOLD
                else -8
            )

            confirmation_score += impact
            negative_confirmations += 1

            if whale_strength >= STRONG_SIGNAL_THRESHOLD:
                hard_blocks.append(
                    "Strong whale distribution opposes the BUY signal"
                )

            _add_check(
                checks,
                "whale_activity",
                False,
                impact,
                whale_state,
                "Whale distribution opposes the BUY signal",
            )

    else:
        if whale_state == "DISTRIBUTION":
            impact = (
                8
                if whale_strength >= STRONG_SIGNAL_THRESHOLD
                else 4
            )

            confirmation_score += impact
            positive_confirmations += 1

            _add_check(
                checks,
                "whale_activity",
                True,
                impact,
                whale_state,
                "Whale distribution supports the SELL signal",
            )

        elif whale_state == "ACCUMULATION":
            impact = (
                -15
                if whale_strength >= STRONG_SIGNAL_THRESHOLD
                else -8
            )

            confirmation_score += impact
            negative_confirmations += 1

            if whale_strength >= STRONG_SIGNAL_THRESHOLD:
                hard_blocks.append(
                    "Strong whale accumulation opposes the SELL signal"
                )

            _add_check(
                checks,
                "whale_activity",
                False,
                impact,
                whale_state,
                "Whale accumulation opposes the SELL signal",
            )

    # ---------------------------------------------------------
    # Iceberg
    # ---------------------------------------------------------

    iceberg_signal = iceberg.get("signal")
    iceberg_strength = _safe_float(
        iceberg.get("strength"),
        0,
    )

    if raw_signal == "BUY":
        if iceberg_signal == "BUY_ICEBERG":
            impact = (
                7
                if iceberg_strength >= 70
                else 4
            )

            confirmation_score += impact
            positive_confirmations += 1

            _add_check(
                checks,
                "iceberg",
                True,
                impact,
                iceberg_signal,
                "Bid-side iceberg candidate supports the BUY signal",
            )

        elif iceberg_signal == "SELL_ICEBERG":
            impact = (
                -12
                if iceberg_strength >= 70
                else -6
            )

            confirmation_score += impact
            negative_confirmations += 1

            _add_check(
                checks,
                "iceberg",
                False,
                impact,
                iceberg_signal,
                "Ask-side iceberg candidate opposes the BUY signal",
            )

    else:
        if iceberg_signal == "SELL_ICEBERG":
            impact = (
                7
                if iceberg_strength >= 70
                else 4
            )

            confirmation_score += impact
            positive_confirmations += 1

            _add_check(
                checks,
                "iceberg",
                True,
                impact,
                iceberg_signal,
                "Ask-side iceberg candidate supports the SELL signal",
            )

        elif iceberg_signal == "BUY_ICEBERG":
            impact = (
                -12
                if iceberg_strength >= 70
                else -6
            )

            confirmation_score += impact
            negative_confirmations += 1

            _add_check(
                checks,
                "iceberg",
                False,
                impact,
                iceberg_signal,
                "Bid-side iceberg candidate opposes the SELL signal",
            )

    # ---------------------------------------------------------
    # Absorption
    # ---------------------------------------------------------

    absorption_signal = absorption.get("signal")
    absorption_strength = _safe_float(
        absorption.get("strength"),
        0,
    )

    if raw_signal == "BUY":
        if absorption_signal == "BUY_ABSORPTION":
            impact = (
                8
                if absorption_strength >= 60
                else 4
            )

            confirmation_score += impact
            positive_confirmations += 1

            _add_check(
                checks,
                "absorption",
                True,
                impact,
                absorption_signal,
                "Buy absorption supports the BUY signal",
            )

        elif absorption_signal == "SELL_ABSORPTION":
            impact = (
                -14
                if absorption_strength >= 60
                else -7
            )

            confirmation_score += impact
            negative_confirmations += 1

            _add_check(
                checks,
                "absorption",
                False,
                impact,
                absorption_signal,
                "Sell absorption opposes the BUY signal",
            )

    else:
        if absorption_signal == "SELL_ABSORPTION":
            impact = (
                8
                if absorption_strength >= 60
                else 4
            )

            confirmation_score += impact
            positive_confirmations += 1

            _add_check(
                checks,
                "absorption",
                True,
                impact,
                absorption_signal,
                "Sell absorption supports the SELL signal",
            )

        elif absorption_signal == "BUY_ABSORPTION":
            impact = (
                -14
                if absorption_strength >= 60
                else -7
            )

            confirmation_score += impact
            negative_confirmations += 1

            _add_check(
                checks,
                "absorption",
                False,
                impact,
                absorption_signal,
                "Buy absorption opposes the SELL signal",
            )

    # ---------------------------------------------------------
    # Liquidity Trend and Sweep
    # ---------------------------------------------------------

    liquidity_signal = liquidity_trend.get("signal")
    sweep_direction = liquidity_sweep.get("direction")
    sweep_confidence = _safe_float(
        liquidity_sweep.get("confidence"),
        0,
    )

    if raw_signal == "BUY":
        if liquidity_signal in [
            "BID_ACCUMULATION",
            "BID_SUPPORT",
        ]:
            confirmation_score += 6
            positive_confirmations += 1

        elif liquidity_signal in [
            "ASK_DISTRIBUTION",
            "BID_WALL_REMOVED",
        ]:
            confirmation_score -= 8
            negative_confirmations += 1

        if (
            sweep_direction == "BULLISH"
            and sweep_confidence >= 60
        ):
            confirmation_score += 6
            positive_confirmations += 1

        elif (
            sweep_direction in [
                "BEARISH",
                "BEARISH_WARNING",
            ]
            and sweep_confidence >= 60
        ):
            confirmation_score -= 12
            negative_confirmations += 1

    else:
        if liquidity_signal in [
            "ASK_DISTRIBUTION",
            "ASK_SUPPORT",
        ]:
            confirmation_score += 6
            positive_confirmations += 1

        elif liquidity_signal in [
            "BID_ACCUMULATION",
            "ASK_WALL_REMOVED",
        ]:
            confirmation_score -= 8
            negative_confirmations += 1

        if (
            sweep_direction == "BEARISH"
            and sweep_confidence >= 60
        ):
            confirmation_score += 6
            positive_confirmations += 1

        elif (
            sweep_direction in [
                "BULLISH",
                "BULLISH_WARNING",
            ]
            and sweep_confidence >= 60
        ):
            confirmation_score -= 12
            negative_confirmations += 1

    # ---------------------------------------------------------
    # Technical and Multi-Timeframe Confirmation
    # ---------------------------------------------------------

    technical_trend = technical.get("trend")
    macd_direction = technical.get("macd_direction")
    mtf_trend = multi_timeframe.get("overall_trend")

    if raw_signal == "BUY":
        if technical_trend == "BULLISH":
            confirmation_score += 6
            positive_confirmations += 1

        elif technical_trend == "BEARISH":
            confirmation_score -= 10
            negative_confirmations += 1

        if macd_direction == "BUY":
            confirmation_score += 5
            positive_confirmations += 1

        elif macd_direction == "SELL":
            confirmation_score -= 8
            negative_confirmations += 1

        if mtf_trend == "BULLISH":
            confirmation_score += 8
            positive_confirmations += 1

        elif mtf_trend == "BEARISH":
            confirmation_score -= 15
            negative_confirmations += 1
            hard_blocks.append(
                "Multi-timeframe trend is bearish"
            )

    else:
        if technical_trend == "BEARISH":
            confirmation_score += 6
            positive_confirmations += 1

        elif technical_trend == "BULLISH":
            confirmation_score -= 10
            negative_confirmations += 1

        if macd_direction == "SELL":
            confirmation_score += 5
            positive_confirmations += 1

        elif macd_direction == "BUY":
            confirmation_score -= 8
            negative_confirmations += 1

        if mtf_trend == "BEARISH":
            confirmation_score += 8
            positive_confirmations += 1

        elif mtf_trend == "BULLISH":
            confirmation_score -= 15
            negative_confirmations += 1
            hard_blocks.append(
                "Multi-timeframe trend is bullish"
            )

    confirmation_score = int(
        max(
            0,
            min(
                100,
                confirmation_score,
            ),
        )
    )

    confirmation_ratio = (
        positive_confirmations
        / (
            positive_confirmations
            + negative_confirmations
        )
        * 100
        if (
            positive_confirmations
            + negative_confirmations
        ) > 0
        else 0
    )

    if hard_blocks:
        decision = "REJECT"
        passed = False

    elif (
        confirmation_score >= APPROVE_THRESHOLD
        and positive_confirmations >= 4
        and confirmation_ratio >= 60
    ):
        decision = "APPROVE"
        passed = True

    elif confirmation_score >= WATCH_THRESHOLD:
        decision = "WATCH"
        passed = False

    else:
        decision = "REJECT"
        passed = False

    reasons = []

    if decision == "APPROVE":
        reasons.append(
            "Independent confirmation layers support the raw AI signal"
        )

    elif decision == "WATCH":
        reasons.append(
            "The setup has some confirmation but is not strong enough for execution"
        )

    else:
        reasons.append(
            "The setup failed one or more confirmation requirements"
        )

    if hard_blocks:
        reasons.append(
            f"{len(hard_blocks)} hard execution block(s) detected"
        )

    return {
        "status": "ready",
        "passed": passed,
        "decision": decision,
        "raw_signal": raw_signal,
        "raw_score": raw_score,
        "confirmation_score": confirmation_score,
        "confirmation_ratio": round(
            confirmation_ratio,
            2,
        ),
        "positive_confirmations": positive_confirmations,
        "negative_confirmations": negative_confirmations,
        "hard_blocks": hard_blocks,
        "warnings": warnings,
        "checks": checks,
        "reasons": reasons,
    }