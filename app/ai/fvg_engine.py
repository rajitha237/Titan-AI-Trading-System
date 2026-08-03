"""
TitanAI Fair Value Gap Engine v1

Detects ICT-style Fair Value Gaps (FVGs) using three-candle imbalances.

Bullish FVG:
- Candle 3 low is above Candle 1 high.

Bearish FVG:
- Candle 3 high is below Candle 1 low.

Also detects:
- Gap size
- Gap percentage
- Whether the gap is filled or unfilled
- Whether current price is inside the gap
- Nearest active bullish and bearish FVG
"""


def _to_float(value) -> float:
    return float(value)


def _get_high(candle) -> float:
    if isinstance(candle, dict):
        return _to_float(candle["high"])
    return _to_float(candle[2])


def _get_low(candle) -> float:
    if isinstance(candle, dict):
        return _to_float(candle["low"])
    return _to_float(candle[3])


def _get_close(candle) -> float:
    if isinstance(candle, dict):
        return _to_float(candle["close"])
    return _to_float(candle[4])


def _get_time(candle):
    if isinstance(candle, dict):
        return (
            candle.get("open_time")
            or candle.get("timestamp")
            or candle.get("time")
        )

    return candle[0] if candle else None


def _price_precision(price: float) -> int:
    price = abs(float(price))

    if price >= 1000:
        return 2
    if price >= 100:
        return 3
    if price >= 10:
        return 4
    if price >= 1:
        return 5
    if price >= 0.1:
        return 6
    if price >= 0.01:
        return 7
    if price >= 0.001:
        return 8

    return 10


def _round_price(value: float, precision: int) -> float:
    return round(float(value), precision)


def _find_bullish_fvg(
    candles: list,
    index: int,
    precision: int,
) -> dict | None:
    first = candles[index - 2]
    third = candles[index]

    first_high = _get_high(first)
    third_low = _get_low(third)

    if third_low <= first_high:
        return None

    lower_bound = first_high
    upper_bound = third_low
    gap_size = upper_bound - lower_bound
    midpoint = lower_bound + gap_size / 2

    return {
        "type": "BULLISH_FVG",
        "direction": "BULLISH",
        "index": index,
        "timestamp": _get_time(third),
        "lower_bound": _round_price(
            lower_bound,
            precision,
        ),
        "upper_bound": _round_price(
            upper_bound,
            precision,
        ),
        "midpoint": _round_price(
            midpoint,
            precision,
        ),
        "gap_size": _round_price(
            gap_size,
            precision,
        ),
        "gap_percent": round(
            gap_size / midpoint * 100
            if midpoint
            else 0,
            4,
        ),
    }


def _find_bearish_fvg(
    candles: list,
    index: int,
    precision: int,
) -> dict | None:
    first = candles[index - 2]
    third = candles[index]

    first_low = _get_low(first)
    third_high = _get_high(third)

    if third_high >= first_low:
        return None

    lower_bound = third_high
    upper_bound = first_low
    gap_size = upper_bound - lower_bound
    midpoint = lower_bound + gap_size / 2

    return {
        "type": "BEARISH_FVG",
        "direction": "BEARISH",
        "index": index,
        "timestamp": _get_time(third),
        "lower_bound": _round_price(
            lower_bound,
            precision,
        ),
        "upper_bound": _round_price(
            upper_bound,
            precision,
        ),
        "midpoint": _round_price(
            midpoint,
            precision,
        ),
        "gap_size": _round_price(
            gap_size,
            precision,
        ),
        "gap_percent": round(
            gap_size / midpoint * 100
            if midpoint
            else 0,
            4,
        ),
    }


def _analyze_fill_status(
    gap: dict,
    candles: list,
    latest_price: float,
    precision: int,
) -> dict:
    start_index = int(gap["index"]) + 1

    lower_bound = float(gap["lower_bound"])
    upper_bound = float(gap["upper_bound"])
    midpoint = float(gap["midpoint"])

    filled = False
    partially_filled = False
    fill_percent = 0.0
    fill_index = None

    if gap["direction"] == "BULLISH":
        lowest_after_gap = None

        for index in range(
            start_index,
            len(candles),
        ):
            candle_low = _get_low(candles[index])

            if (
                lowest_after_gap is None
                or candle_low < lowest_after_gap
            ):
                lowest_after_gap = candle_low

            if candle_low <= lower_bound:
                filled = True
                fill_index = index
                fill_percent = 100.0
                break

        if not filled and lowest_after_gap is not None:
            penetration = upper_bound - lowest_after_gap
            gap_size = upper_bound - lower_bound

            if penetration > 0 and gap_size > 0:
                fill_percent = min(
                    100.0,
                    penetration / gap_size * 100,
                )
                partially_filled = fill_percent > 0

    else:
        highest_after_gap = None

        for index in range(
            start_index,
            len(candles),
        ):
            candle_high = _get_high(candles[index])

            if (
                highest_after_gap is None
                or candle_high > highest_after_gap
            ):
                highest_after_gap = candle_high

            if candle_high >= upper_bound:
                filled = True
                fill_index = index
                fill_percent = 100.0
                break

        if not filled and highest_after_gap is not None:
            penetration = highest_after_gap - lower_bound
            gap_size = upper_bound - lower_bound

            if penetration > 0 and gap_size > 0:
                fill_percent = min(
                    100.0,
                    penetration / gap_size * 100,
                )
                partially_filled = fill_percent > 0

    price_inside_gap = (
        lower_bound
        <= latest_price
        <= upper_bound
    )

    midpoint_retested = False

    if gap["direction"] == "BULLISH":
        midpoint_retested = latest_price <= midpoint
    else:
        midpoint_retested = latest_price >= midpoint

    return {
        **gap,
        "filled": filled,
        "partially_filled": partially_filled,
        "fill_percent": round(
            fill_percent,
            2,
        ),
        "fill_index": fill_index,
        "active": not filled,
        "price_inside_gap": price_inside_gap,
        "midpoint_retested": midpoint_retested,
        "distance_from_gap": _round_price(
            0.0
            if price_inside_gap
            else (
                latest_price - upper_bound
                if latest_price > upper_bound
                else lower_bound - latest_price
            ),
            precision,
        ),
    }


def analyze_fair_value_gaps(
    candles: list,
    minimum_gap_percent: float = 0.02,
    max_returned_gaps: int = 10,
) -> dict:
    if not candles or len(candles) < 10:
        return {
            "status": "collecting",
            "signal": "NEUTRAL",
            "direction": "NONE",
            "reason": "Not enough candle data",
            "bullish_gaps": [],
            "bearish_gaps": [],
        }

    latest_price = _get_close(candles[-1])
    precision = _price_precision(latest_price)

    detected_gaps = []

    for index in range(2, len(candles)):
        bullish_gap = _find_bullish_fvg(
            candles=candles,
            index=index,
            precision=precision,
        )

        if (
            bullish_gap
            and bullish_gap["gap_percent"]
            >= minimum_gap_percent
        ):
            detected_gaps.append(bullish_gap)

        bearish_gap = _find_bearish_fvg(
            candles=candles,
            index=index,
            precision=precision,
        )

        if (
            bearish_gap
            and bearish_gap["gap_percent"]
            >= minimum_gap_percent
        ):
            detected_gaps.append(bearish_gap)

    analyzed_gaps = [
        _analyze_fill_status(
            gap=gap,
            candles=candles,
            latest_price=latest_price,
            precision=precision,
        )
        for gap in detected_gaps
    ]

    active_bullish = [
        gap
        for gap in analyzed_gaps
        if (
            gap["direction"] == "BULLISH"
            and gap["active"] is True
        )
    ]

    active_bearish = [
        gap
        for gap in analyzed_gaps
        if (
            gap["direction"] == "BEARISH"
            and gap["active"] is True
        )
    ]

    active_bullish.sort(
        key=lambda gap: (
            abs(
                latest_price
                - float(gap["midpoint"])
            ),
            -int(gap["index"]),
        )
    )

    active_bearish.sort(
        key=lambda gap: (
            abs(
                latest_price
                - float(gap["midpoint"])
            ),
            -int(gap["index"]),
        )
    )

    nearest_bullish = (
        active_bullish[0]
        if active_bullish
        else None
    )

    nearest_bearish = (
        active_bearish[0]
        if active_bearish
        else None
    )

    signal = "NEUTRAL"
    direction = "NONE"
    strength = 0
    reasons = []

    bullish_inside = (
        nearest_bullish
        and nearest_bullish["price_inside_gap"]
    )

    bearish_inside = (
        nearest_bearish
        and nearest_bearish["price_inside_gap"]
    )

    if bullish_inside and not bearish_inside:
        signal = "BULLISH_FVG_RETEST"
        direction = "BULLISH"
        strength = 80
        reasons.append(
            "Price is retesting an active bullish fair value gap"
        )

        if nearest_bullish["midpoint_retested"]:
            strength = 90
            reasons.append(
                "Price has reached the bullish FVG midpoint"
            )

    elif bearish_inside and not bullish_inside:
        signal = "BEARISH_FVG_RETEST"
        direction = "BEARISH"
        strength = 80
        reasons.append(
            "Price is retesting an active bearish fair value gap"
        )

        if nearest_bearish["midpoint_retested"]:
            strength = 90
            reasons.append(
                "Price has reached the bearish FVG midpoint"
            )

    elif nearest_bullish and nearest_bearish:
        bullish_distance = float(
            nearest_bullish["distance_from_gap"]
        )
        bearish_distance = float(
            nearest_bearish["distance_from_gap"]
        )

        if bullish_distance < bearish_distance:
            signal = "BULLISH_FVG_NEARBY"
            direction = "BULLISH"
            strength = 60
            reasons.append(
                "Nearest active fair value gap is bullish"
            )
        elif bearish_distance < bullish_distance:
            signal = "BEARISH_FVG_NEARBY"
            direction = "BEARISH"
            strength = 60
            reasons.append(
                "Nearest active fair value gap is bearish"
            )
        else:
            reasons.append(
                "Bullish and bearish FVGs are equally near"
            )

    elif nearest_bullish:
        signal = "BULLISH_FVG_NEARBY"
        direction = "BULLISH"
        strength = 60
        reasons.append(
            "An active bullish fair value gap is nearby"
        )

    elif nearest_bearish:
        signal = "BEARISH_FVG_NEARBY"
        direction = "BEARISH"
        strength = 60
        reasons.append(
            "An active bearish fair value gap is nearby"
        )

    else:
        reasons.append(
            "No active fair value gap detected"
        )

    bullish_gaps = [
        gap
        for gap in analyzed_gaps
        if gap["direction"] == "BULLISH"
    ][-max_returned_gaps:]

    bearish_gaps = [
        gap
        for gap in analyzed_gaps
        if gap["direction"] == "BEARISH"
    ][-max_returned_gaps:]

    return {
        "status": "ready",
        "signal": signal,
        "direction": direction,
        "strength": strength,
        "latest_price": _round_price(
            latest_price,
            precision,
        ),
        "price_precision": precision,
        "minimum_gap_percent": minimum_gap_percent,
        "total_gaps": len(analyzed_gaps),
        "active_bullish_count": len(
            active_bullish
        ),
        "active_bearish_count": len(
            active_bearish
        ),
        "nearest_bullish_gap": nearest_bullish,
        "nearest_bearish_gap": nearest_bearish,
        "bullish_gaps": bullish_gaps,
        "bearish_gaps": bearish_gaps,
        "reasons": reasons,
    }