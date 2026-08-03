"""
TitanAI VWAP Engine v1

Calculates volume-weighted average price and institutional bias.

Features:
- VWAP
- Price above/below VWAP
- Distance from VWAP
- Mean-reversion warning
- Trend confirmation
- Dynamic price precision
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


def _get_volume(candle) -> float:
    if isinstance(candle, dict):
        return _to_float(candle["volume"])
    return _to_float(candle[5])


def get_price_precision(price: float) -> int:
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


def analyze_vwap(
    candles: list,
    mean_reversion_threshold_percent: float = 1.5,
) -> dict:
    if not candles or len(candles) < 20:
        return {
            "status": "collecting",
            "signal": "NEUTRAL",
            "bias": "UNKNOWN",
            "reason": "Not enough candle data",
        }

    cumulative_price_volume = 0.0
    cumulative_volume = 0.0
    vwap_series = []

    for candle in candles:
        high = _get_high(candle)
        low = _get_low(candle)
        close = _get_close(candle)
        volume = _get_volume(candle)

        typical_price = (high + low + close) / 3

        cumulative_price_volume += typical_price * volume
        cumulative_volume += volume

        current_vwap = (
            cumulative_price_volume / cumulative_volume
            if cumulative_volume > 0
            else typical_price
        )

        vwap_series.append(current_vwap)

    latest_price = _get_close(candles[-1])
    current_vwap = vwap_series[-1]

    precision = get_price_precision(latest_price)

    distance = latest_price - current_vwap

    distance_percent = (
        distance / current_vwap * 100
        if current_vwap
        else 0
    )

    recent_vwap_values = vwap_series[-10:]

    if len(recent_vwap_values) >= 2:
        vwap_slope = (
            recent_vwap_values[-1]
            - recent_vwap_values[0]
        )
    else:
        vwap_slope = 0

    if vwap_slope > 0:
        vwap_trend = "RISING"
    elif vwap_slope < 0:
        vwap_trend = "FALLING"
    else:
        vwap_trend = "FLAT"

    if latest_price > current_vwap:
        bias = "ABOVE_VWAP"
        signal = "BULLISH"
    elif latest_price < current_vwap:
        bias = "BELOW_VWAP"
        signal = "BEARISH"
    else:
        bias = "AT_VWAP"
        signal = "NEUTRAL"

    mean_reversion_warning = False
    mean_reversion_direction = "NONE"

    if distance_percent >= mean_reversion_threshold_percent:
        mean_reversion_warning = True
        mean_reversion_direction = "DOWN"
    elif distance_percent <= -mean_reversion_threshold_percent:
        mean_reversion_warning = True
        mean_reversion_direction = "UP"

    if (
        signal == "BULLISH"
        and vwap_trend == "RISING"
        and not mean_reversion_warning
    ):
        strength = 85
    elif (
        signal == "BEARISH"
        and vwap_trend == "FALLING"
        and not mean_reversion_warning
    ):
        strength = 85
    elif signal in ["BULLISH", "BEARISH"]:
        strength = 65
    else:
        strength = 40

    reasons = []

    if bias == "ABOVE_VWAP":
        reasons.append("Price is trading above VWAP")
    elif bias == "BELOW_VWAP":
        reasons.append("Price is trading below VWAP")
    else:
        reasons.append("Price is trading near VWAP")

    if vwap_trend == "RISING":
        reasons.append("VWAP trend is rising")
    elif vwap_trend == "FALLING":
        reasons.append("VWAP trend is falling")
    else:
        reasons.append("VWAP trend is flat")

    if mean_reversion_warning:
        reasons.append(
            "Price is extended from VWAP and may mean-revert"
        )

    return {
        "status": "ready",
        "signal": signal,
        "bias": bias,
        "strength": strength,
        "latest_price": round(latest_price, precision),
        "vwap": round(current_vwap, precision),
        "distance_from_vwap": round(distance, precision),
        "distance_percent": round(distance_percent, 4),
        "vwap_trend": vwap_trend,
        "vwap_slope": round(vwap_slope, precision),
        "mean_reversion_warning": mean_reversion_warning,
        "mean_reversion_direction": mean_reversion_direction,
        "mean_reversion_threshold_percent": (
            mean_reversion_threshold_percent
        ),
        "price_precision": precision,
        "total_volume": round(cumulative_volume, 2),
        "reasons": reasons,
    }