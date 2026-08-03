"""
TitanAI Scoring Engine v13

Institutional Order Flow + Smart Money Structure
+ Volume Profile + VWAP + Fair Value Gaps.
"""


def calculate_ai_score(
    order_book: dict,
    order_flow: dict,
    liquidity_trend: dict | None,
    liquidity_sweep: dict | None,
    absorption: dict | None,
    iceberg: dict | None,
    whale_activity: dict | None,
    market_structure: dict | None,
    volume_profile: dict | None,
    vwap: dict | None,
    fair_value_gaps: dict | None,
    open_interest: dict,
    funding_rate: dict,
    technical: dict,
    multi_timeframe: dict,
) -> dict:
    score = 50
    reasons = []

    breakdown = {
        "base": 50,
        "order_book": 0,
        "order_flow": 0,
        "liquidity": 0,
        "liquidity_sweep": 0,
        "absorption": 0,
        "iceberg": 0,
        "whales": 0,
        "market_structure": 0,
        "volume_profile": 0,
        "vwap": 0,
        "fair_value_gap": 0,
        "funding": 0,
        "open_interest": 0,
        "technical": 0,
        "multi_timeframe": 0,
    }

    order_book = order_book or {}
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
    open_interest = open_interest or {}
    funding_rate = funding_rate or {}
    technical = technical or {}
    multi_timeframe = multi_timeframe or {}

    # ---------------------------------------------------------
    # Order Book
    # ---------------------------------------------------------

    pressure = order_book.get("pressure")

    if pressure == "BUY_PRESSURE":
        score += 10
        breakdown["order_book"] += 10
        reasons.append("Order book shows buy pressure")

    elif pressure == "SELL_PRESSURE":
        score -= 12
        breakdown["order_book"] -= 12
        reasons.append("Order book shows sell pressure")

    else:
        reasons.append("Order book is neutral")

    # ---------------------------------------------------------
    # Order Flow
    # ---------------------------------------------------------

    flow_pressure = order_flow.get("pressure")

    if flow_pressure == "AGGRESSIVE_BUYERS":
        score += 12
        breakdown["order_flow"] += 12
        reasons.append("Aggressive buyers detected")

    elif flow_pressure == "AGGRESSIVE_SELLERS":
        score -= 15
        breakdown["order_flow"] -= 15
        reasons.append("Aggressive sellers detected")

    else:
        score += 3
        breakdown["order_flow"] += 3
        reasons.append("Order flow is balanced")

    # ---------------------------------------------------------
    # Recent Whale Trades
    # ---------------------------------------------------------

    whale_trades = order_flow.get("whale_trades", [])

    whale_buy_count = len(
        [
            trade
            for trade in whale_trades
            if trade.get("side") == "BUY"
        ]
    )

    whale_sell_count = len(
        [
            trade
            for trade in whale_trades
            if trade.get("side") == "SELL"
        ]
    )

    if whale_buy_count > whale_sell_count:
        score += 5
        breakdown["whales"] += 5
        reasons.append("Recent whale trades support buyers")

    elif whale_sell_count > whale_buy_count:
        score -= 5
        breakdown["whales"] -= 5
        reasons.append("Recent whale trades support sellers")

    # ---------------------------------------------------------
    # Whale Accumulation / Distribution
    # ---------------------------------------------------------

    whale_state = whale_activity.get("state")
    whale_strength = float(
        whale_activity.get("strength") or 0
    )
    whale_samples = int(
        whale_activity.get("samples") or 0
    )

    if whale_samples < 5:
        reasons.append(
            "Whale engine still collecting samples"
        )

    elif whale_state == "ACCUMULATION":
        whale_add = 10 if whale_strength >= 70 else 6

        score += whale_add
        breakdown["whales"] += whale_add
        reasons.append("Whale accumulation detected")

    elif whale_state == "DISTRIBUTION":
        whale_deduction = (
            12 if whale_strength >= 70 else 7
        )

        score -= whale_deduction
        breakdown["whales"] -= whale_deduction
        reasons.append("Whale distribution detected")

    else:
        reasons.append("Whale activity neutral")

    # ---------------------------------------------------------
    # Liquidity Trend
    # ---------------------------------------------------------

    liquidity_signal = liquidity_trend.get("signal")
    latest_liquidity_pressure = liquidity_trend.get(
        "latest_pressure"
    )

    if liquidity_signal in [
        "BID_ACCUMULATION",
        "BID_SUPPORT",
    ]:
        score += 8
        breakdown["liquidity"] += 8
        reasons.append("Bid liquidity accumulation")

    elif liquidity_signal in [
        "ASK_DISTRIBUTION",
        "ASK_WALL_REMOVED",
        "BID_WALL_REMOVED",
    ]:
        score -= 8
        breakdown["liquidity"] -= 8
        reasons.append(
            "Bearish or weak liquidity behaviour"
        )

    else:
        reasons.append("Liquidity trend neutral")

    # ---------------------------------------------------------
    # Liquidity Sweep
    # ---------------------------------------------------------

    sweep_direction = liquidity_sweep.get("direction")
    sweep_signal = liquidity_sweep.get("signal")
    sweep_confidence = float(
        liquidity_sweep.get("confidence") or 0
    )

    if (
        sweep_direction == "BULLISH"
        and sweep_confidence >= 60
    ):
        score += 6
        breakdown["liquidity_sweep"] += 6
        reasons.append("Bullish liquidity sweep detected")

    elif (
        sweep_direction in [
            "BEARISH",
            "BEARISH_WARNING",
        ]
        and sweep_confidence >= 60
    ):
        score -= 10
        breakdown["liquidity_sweep"] -= 10
        reasons.append("Bearish liquidity sweep detected")

    else:
        reasons.append("Liquidity sweep neutral")

    # ---------------------------------------------------------
    # Absorption
    # ---------------------------------------------------------

    absorption_signal = absorption.get("signal")
    absorption_strength = float(
        absorption.get("strength") or 0
    )

    if absorption_signal == "BUY_ABSORPTION":
        absorption_add = (
            8 if absorption_strength >= 60 else 5
        )

        score += absorption_add
        breakdown["absorption"] += absorption_add
        reasons.append("Buy absorption detected")

    elif absorption_signal == "SELL_ABSORPTION":
        absorption_deduction = (
            10 if absorption_strength >= 60 else 6
        )

        score -= absorption_deduction
        breakdown["absorption"] -= absorption_deduction
        reasons.append("Sell absorption detected")

    else:
        reasons.append("Absorption neutral")

    # ---------------------------------------------------------
    # Iceberg
    # ---------------------------------------------------------

    iceberg_signal = iceberg.get("signal")
    iceberg_strength = float(
        iceberg.get("strength") or 0
    )

    if iceberg_signal == "BUY_ICEBERG":
        iceberg_add = (
            8 if iceberg_strength >= 60 else 5
        )

        score += iceberg_add
        breakdown["iceberg"] += iceberg_add
        reasons.append("Buy iceberg detected")

    elif iceberg_signal == "SELL_ICEBERG":
        iceberg_deduction = (
            10 if iceberg_strength >= 60 else 6
        )

        score -= iceberg_deduction
        breakdown["iceberg"] -= iceberg_deduction
        reasons.append("Sell iceberg detected")

    elif iceberg_signal == "BALANCED_ICEBERG_ACTIVITY":
        reasons.append(
            "Balanced iceberg-style liquidity detected"
        )

    else:
        reasons.append("No iceberg detected")

    # ---------------------------------------------------------
    # Market Structure
    # ---------------------------------------------------------

    structure = market_structure.get("structure")
    structure_signal = market_structure.get("signal")
    structure_direction = market_structure.get(
        "direction"
    )
    bos = bool(market_structure.get("bos"))
    choch = bool(market_structure.get("choch"))

    if structure == "BULLISH":
        score += 8
        breakdown["market_structure"] += 8
        reasons.append("Bullish market structure")

    elif structure == "BEARISH":
        score -= 8
        breakdown["market_structure"] -= 8
        reasons.append("Bearish market structure")

    else:
        reasons.append(
            "Market structure neutral or mixed"
        )

    if structure_signal == "BULLISH_BOS":
        score += 12
        breakdown["market_structure"] += 12
        reasons.append(
            "Bullish break of structure detected"
        )

    elif structure_signal == "BEARISH_BOS":
        score -= 12
        breakdown["market_structure"] -= 12
        reasons.append(
            "Bearish break of structure detected"
        )

    elif structure_signal == "BULLISH_CHOCH":
        score += 15
        breakdown["market_structure"] += 15
        reasons.append(
            "Bullish change of character detected"
        )

    elif structure_signal == "BEARISH_CHOCH":
        score -= 15
        breakdown["market_structure"] -= 15
        reasons.append(
            "Bearish change of character detected"
        )

    # ---------------------------------------------------------
    # Volume Profile
    # ---------------------------------------------------------

    profile_status = volume_profile.get("status")
    profile_signal = volume_profile.get("signal")
    profile_bias = volume_profile.get("bias")
    profile_acceptance = volume_profile.get(
        "acceptance"
    )

    if profile_status != "ready":
        reasons.append(
            "Volume profile is collecting data"
        )

    elif profile_signal == "BULLISH":
        score += 8
        breakdown["volume_profile"] += 8
        reasons.append(
            "Price is above volume value area"
        )

        if profile_acceptance == "ABOVE_POC":
            score += 3
            breakdown["volume_profile"] += 3
            reasons.append(
                "Price is accepted above POC"
            )

    elif profile_signal == "BEARISH":
        score -= 8
        breakdown["volume_profile"] -= 8
        reasons.append(
            "Price is below volume value area"
        )

        if profile_acceptance == "BELOW_POC":
            score -= 3
            breakdown["volume_profile"] -= 3
            reasons.append(
                "Price is accepted below POC"
            )

    else:
        reasons.append(
            "Price is inside volume value area"
        )

    # ---------------------------------------------------------
    # VWAP
    # ---------------------------------------------------------

    vwap_status = vwap.get("status")
    vwap_signal = vwap.get("signal")
    vwap_bias = vwap.get("bias")
    vwap_trend = vwap.get("vwap_trend")

    vwap_strength = float(
        vwap.get("strength") or 0
    )

    vwap_distance_percent = float(
        vwap.get("distance_percent") or 0
    )

    mean_reversion_warning = bool(
        vwap.get("mean_reversion_warning")
    )

    if vwap_status != "ready":
        reasons.append("VWAP engine is collecting data")

    elif vwap_signal == "BULLISH":
        vwap_add = (
            8
            if (
                vwap_trend == "RISING"
                and vwap_strength >= 80
            )
            else 5
        )

        score += vwap_add
        breakdown["vwap"] += vwap_add
        reasons.append("Price is above VWAP")

        if vwap_trend == "RISING":
            reasons.append("VWAP is rising")

    elif vwap_signal == "BEARISH":
        vwap_deduction = (
            8
            if (
                vwap_trend == "FALLING"
                and vwap_strength >= 80
            )
            else 5
        )

        score -= vwap_deduction
        breakdown["vwap"] -= vwap_deduction
        reasons.append("Price is below VWAP")

        if vwap_trend == "FALLING":
            reasons.append("VWAP is falling")

    else:
        reasons.append("Price is near VWAP")

    if mean_reversion_warning:
        if vwap_distance_percent > 0:
            score -= 4
            breakdown["vwap"] -= 4
            reasons.append(
                "Price is overextended above VWAP"
            )

        elif vwap_distance_percent < 0:
            score += 2
            breakdown["vwap"] += 2
            reasons.append(
                "Price is extended below VWAP"
            )

    # ---------------------------------------------------------
    # Fair Value Gaps
    # ---------------------------------------------------------

    fvg_status = fair_value_gaps.get("status")
    fvg_signal = fair_value_gaps.get("signal")
    fvg_direction = fair_value_gaps.get("direction")
    fvg_strength = float(
        fair_value_gaps.get("strength") or 0
    )

    if fvg_status != "ready":
        reasons.append(
            "Fair value gap engine is collecting data"
        )

    elif fvg_signal == "BULLISH_FVG_RETEST":
        score += 10
        breakdown["fair_value_gap"] += 10
        reasons.append(
            "Bullish fair value gap retest detected"
        )

    elif fvg_signal == "BULLISH_FVG_NEARBY":
        score += 5
        breakdown["fair_value_gap"] += 5
        reasons.append(
            "Bullish fair value gap is nearby"
        )

    elif fvg_signal == "BEARISH_FVG_RETEST":
        score -= 12
        breakdown["fair_value_gap"] -= 12
        reasons.append(
            "Bearish fair value gap retest detected"
        )

    elif fvg_signal == "BEARISH_FVG_NEARBY":
        score -= 6
        breakdown["fair_value_gap"] -= 6
        reasons.append(
            "Bearish fair value gap is nearby"
        )

    else:
        reasons.append(
            "Fair value gap signal is neutral"
        )

    # ---------------------------------------------------------
    # Funding Rate
    # ---------------------------------------------------------

    funding = float(
        funding_rate.get(
            "last_funding_rate",
            0,
        )
        or 0
    )

    if funding > 0.0005:
        score -= 8
        breakdown["funding"] -= 8
        reasons.append(
            "Funding rate is high positive"
        )

    elif funding < -0.0005:
        score += 5
        breakdown["funding"] += 5
        reasons.append("Funding rate is negative")

    else:
        reasons.append("Funding rate is normal")

    # ---------------------------------------------------------
    # Open Interest
    # ---------------------------------------------------------

    open_interest_value = float(
        open_interest.get(
            "open_interest",
            0,
        )
        or 0
    )

    if open_interest_value > 0:
        score += 5
        breakdown["open_interest"] += 5
        reasons.append(
            "Open interest data available"
        )

    # ---------------------------------------------------------
    # Technical Trend
    # ---------------------------------------------------------

    trend = technical.get("trend")

    if trend == "BULLISH":
        score += 12
        breakdown["technical"] += 12
        reasons.append("EMA trend bullish")

    elif trend == "BEARISH":
        score -= 12
        breakdown["technical"] -= 12
        reasons.append("EMA trend bearish")

    # ---------------------------------------------------------
    # RSI
    # ---------------------------------------------------------

    rsi_signal = technical.get("rsi_signal")

    if rsi_signal == "OVERSOLD":
        score += 8
        breakdown["technical"] += 8
        reasons.append("RSI oversold")

    elif rsi_signal == "OVERBOUGHT":
        score -= 8
        breakdown["technical"] -= 8
        reasons.append("RSI overbought")

    else:
        reasons.append("RSI neutral")

    # ---------------------------------------------------------
    # MACD
    # ---------------------------------------------------------

    macd_direction = technical.get(
        "macd_direction"
    )

    if macd_direction == "BUY":
        score += 12
        breakdown["technical"] += 12
        reasons.append("MACD buy")

    elif macd_direction == "SELL":
        score -= 12
        breakdown["technical"] -= 12
        reasons.append("MACD sell")

    # ---------------------------------------------------------
    # Multi-Timeframe
    # ---------------------------------------------------------

    mtf_trend = multi_timeframe.get(
        "overall_trend"
    )

    if mtf_trend == "BULLISH":
        score += 15
        breakdown["multi_timeframe"] += 15
        reasons.append("Multi-timeframe bullish")

    elif mtf_trend == "BEARISH":
        score -= 15
        breakdown["multi_timeframe"] -= 15
        reasons.append("Multi-timeframe bearish")

    else:
        reasons.append("Multi-timeframe mixed")

    # ---------------------------------------------------------
    # Safety Caps
    # ---------------------------------------------------------

    if (
        flow_pressure == "AGGRESSIVE_SELLERS"
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because aggressive sellers detected"
        )

    if (
        pressure == "SELL_PRESSURE"
        and latest_liquidity_pressure
        == "ASK_LIQUIDITY_STRONG"
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because sell pressure and ask liquidity are strong"
        )

    if (
        sweep_direction in [
            "BEARISH",
            "BEARISH_WARNING",
        ]
        and sweep_confidence >= 60
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because bearish liquidity sweep detected"
        )

    if (
        absorption_signal == "SELL_ABSORPTION"
        and absorption_strength >= 60
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because sell absorption detected"
        )

    if (
        iceberg_signal == "SELL_ICEBERG"
        and iceberg_strength >= 60
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because sell iceberg detected"
        )

    if (
        whale_samples >= 5
        and whale_state == "DISTRIBUTION"
        and whale_strength >= 70
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because whale distribution detected"
        )

    if (
        structure_signal in [
            "BEARISH_BOS",
            "BEARISH_CHOCH",
        ]
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because bearish market structure detected"
        )

    if (
        profile_status == "ready"
        and profile_bias == "BELOW_VALUE"
        and profile_acceptance == "BELOW_POC"
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because price is accepted below the value area"
        )

    if (
        vwap_status == "ready"
        and vwap_bias == "BELOW_VWAP"
        and vwap_trend == "FALLING"
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because price is below a falling VWAP"
        )

    if (
        fvg_signal == "BEARISH_FVG_RETEST"
        and fvg_strength >= 80
        and score > 74
    ):
        score = 74
        reasons.append(
            "BUY score capped because price is retesting a bearish fair value gap"
        )

    score = max(
        0,
        min(score, 100),
    )

    if score >= 75:
        signal = "BUY"

    elif score <= 35:
        signal = "SELL"

    else:
        signal = "HOLD"

    return {
        "score": score,
        "signal": signal,
        "reasons": reasons,
        "breakdown": breakdown,

        "order_flow": {
            "pressure": flow_pressure,
            "delta_ratio": order_flow.get(
                "delta_ratio"
            ),
            "whale_buy_count": whale_buy_count,
            "whale_sell_count": whale_sell_count,
        },

        "liquidity": liquidity_trend,

        "liquidity_sweep": {
            "signal": sweep_signal,
            "direction": sweep_direction,
            "confidence": sweep_confidence,
        },

        "absorption": absorption,
        "iceberg": iceberg,
        "whale_activity": whale_activity,

        "market_structure": {
            "structure": structure,
            "signal": structure_signal,
            "direction": structure_direction,
            "bos": bos,
            "choch": choch,
        },

        "volume_profile": volume_profile,
        "vwap": vwap,
        "fair_value_gaps": fair_value_gaps,
    }