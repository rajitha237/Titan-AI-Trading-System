"""
TitanAI Volume Profile Engine v2

Precision-safe Volume Profile for both high-priced and low-priced assets.

Features:
- Point of Control (POC)
- High Volume Nodes (HVN)
- Low Volume Nodes (LVN)
- Value Area High (VAH)
- Value Area Low (VAL)
- Dynamic price precision
- Acceptance around POC
- Institutional bias
"""

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP


def _to_float(value) -> float:
    return float(value)


def _get_close(candle) -> float:
    if isinstance(candle, dict):
        return _to_float(candle["close"])

    return _to_float(candle[4])


def _get_volume(candle) -> float:
    if isinstance(candle, dict):
        return _to_float(candle["volume"])

    return _to_float(candle[5])


def get_price_precision(price: float) -> int:
    """
    Select a display precision appropriate for the asset price.
    """

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


def round_price(price: float, precision: int) -> float:
    """
    Decimal-based rounding to reduce floating-point precision problems.
    """

    quantizer = Decimal("1").scaleb(-precision)

    rounded = Decimal(str(price)).quantize(
        quantizer,
        rounding=ROUND_HALF_UP,
    )

    return float(rounded)


def analyze_volume_profile(
    candles: list,
    bins: int = 40,
    value_area_percent: float = 0.70,
) -> dict:
    if not candles or len(candles) < 20:
        return {
            "status": "collecting",
            "reason": "Not enough candles",
        }

    if bins <= 1:
        raise ValueError("bins must be greater than 1")

    closes = [_get_close(candle) for candle in candles]
    volumes = [_get_volume(candle) for candle in candles]

    low_price = min(closes)
    high_price = max(closes)
    latest_price = closes[-1]

    if high_price <= low_price:
        return {
            "status": "collecting",
            "reason": "Flat market",
        }

    precision = get_price_precision(latest_price)
    step = (high_price - low_price) / bins

    if step <= 0:
        return {
            "status": "collecting",
            "reason": "Invalid profile step",
        }

    profile = defaultdict(float)

    for close, volume in zip(closes, volumes):
        bucket_index = int((close - low_price) / step)

        bucket_index = max(
            0,
            min(bucket_index, bins - 1),
        )

        bucket_midpoint = (
            low_price
            + bucket_index * step
            + step / 2
        )

        bucket_price = round_price(
            bucket_midpoint,
            precision,
        )

        profile[bucket_price] += volume

    if not profile:
        return {
            "status": "collecting",
            "reason": "Volume profile is empty",
        }

    profile_by_volume = sorted(
        profile.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    poc_price, poc_volume = profile_by_volume[0]

    total_volume = sum(profile.values())
    target_volume = total_volume * value_area_percent

    accumulated_volume = 0.0
    value_area_prices = []

    for price, volume in profile_by_volume:
        value_area_prices.append(price)
        accumulated_volume += volume

        if accumulated_volume >= target_volume:
            break

    value_area_high = max(value_area_prices)
    value_area_low = min(value_area_prices)

    high_volume_nodes = [
        {
            "price": round_price(price, precision),
            "volume": round(volume, 2),
        }
        for price, volume in profile_by_volume[:5]
    ]

    low_volume_nodes = [
        {
            "price": round_price(price, precision),
            "volume": round(volume, 2),
        }
        for price, volume in profile_by_volume[-5:]
    ]

    distance_from_poc = latest_price - poc_price
    distance_from_poc_percent = (
        distance_from_poc / poc_price * 100
        if poc_price
        else 0
    )

    poc_tolerance = max(step, abs(poc_price) * 0.001)

    if abs(distance_from_poc) <= poc_tolerance:
        acceptance = "AT_POC"
    elif latest_price > poc_price:
        acceptance = "ABOVE_POC"
    else:
        acceptance = "BELOW_POC"

    if latest_price > value_area_high:
        bias = "ABOVE_VALUE"
        signal = "BULLISH"
    elif latest_price < value_area_low:
        bias = "BELOW_VALUE"
        signal = "BEARISH"
    else:
        bias = "INSIDE_VALUE"
        signal = "NEUTRAL"

    reasons = []

    if bias == "ABOVE_VALUE":
        reasons.append("Price trading above value area")
    elif bias == "BELOW_VALUE":
        reasons.append("Price trading below value area")
    else:
        reasons.append("Price trading inside value area")

    if acceptance == "AT_POC":
        reasons.append("Market accepting fair value near POC")
    elif acceptance == "ABOVE_POC":
        reasons.append("Market trading above Point of Control")
    else:
        reasons.append("Market trading below Point of Control")

    return {
        "status": "ready",
        "signal": signal,
        "bias": bias,
        "latest_price": round_price(
            latest_price,
            precision,
        ),
        "price_precision": precision,
        "bin_count": bins,
        "bin_size": round_price(step, precision),
        "point_of_control": round_price(
            poc_price,
            precision,
        ),
        "point_of_control_volume": round(
            poc_volume,
            2,
        ),
        "value_area_high": round_price(
            value_area_high,
            precision,
        ),
        "value_area_low": round_price(
            value_area_low,
            precision,
        ),
        "value_area_percent": round(
            value_area_percent * 100,
            2,
        ),
        "acceptance": acceptance,
        "distance_from_poc": round_price(
            distance_from_poc,
            precision,
        ),
        "distance_from_poc_percent": round(
            distance_from_poc_percent,
            4,
        ),
        "high_volume_nodes": high_volume_nodes,
        "low_volume_nodes": low_volume_nodes,
        "total_profile_volume": round(
            total_volume,
            2,
        ),
        "reasons": reasons,
    }