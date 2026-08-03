"""
TitanAI Market Structure Engine v1

Detects:
- Higher High / Higher Low
- Lower High / Lower Low
- Bullish / Bearish structure
- BOS (Break of Structure)
- CHoCH (Change of Character)
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


def find_swings(
    candles: list,
    lookback: int = 3,
) -> dict:
    swing_highs = []
    swing_lows = []

    if len(candles) < lookback * 2 + 1:
        return {
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
        }

    for i in range(lookback, len(candles) - lookback):
        high = _get_high(candles[i])
        low = _get_low(candles[i])

        left = candles[i - lookback:i]
        right = candles[i + 1:i + lookback + 1]

        if high > max(_get_high(c) for c in left + right):
            swing_highs.append({
                "index": i,
                "price": high,
            })

        if low < min(_get_low(c) for c in left + right):
            swing_lows.append({
                "index": i,
                "price": low,
            })

    return {
        "swing_highs": swing_highs[-10:],
        "swing_lows": swing_lows[-10:],
    }


def analyze_market_structure(
    candles: list,
    lookback: int = 3,
) -> dict:
    swings = find_swings(candles, lookback)

    swing_highs = swings["swing_highs"]
    swing_lows = swings["swing_lows"]

    latest_close = _get_close(candles[-1]) if candles else None

    structure = "UNKNOWN"
    signal = "NEUTRAL"
    bos = False
    choch = False
    direction = "NONE"
    reasons = []

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {
            "status": "collecting",
            "structure": structure,
            "signal": signal,
            "direction": direction,
            "bos": bos,
            "choch": choch,
            "latest_close": latest_close,
            "swing_highs": swing_highs,
            "swing_lows": swing_lows,
            "reasons": ["Not enough swing points"],
        }

    last_high = swing_highs[-1]["price"]
    prev_high = swing_highs[-2]["price"]

    last_low = swing_lows[-1]["price"]
    prev_low = swing_lows[-2]["price"]

    higher_high = last_high > prev_high
    higher_low = last_low > prev_low
    lower_high = last_high < prev_high
    lower_low = last_low < prev_low

    if higher_high and higher_low:
        structure = "BULLISH"
        reasons.append("Higher high and higher low detected")
    elif lower_high and lower_low:
        structure = "BEARISH"
        reasons.append("Lower high and lower low detected")
    else:
        structure = "MIXED"
        reasons.append("Mixed market structure")

    if latest_close is not None and latest_close > last_high:
        bos = True
        direction = "BULLISH"
        signal = "BULLISH_BOS"
        reasons.append("Close broke above latest swing high")

    elif latest_close is not None and latest_close < last_low:
        bos = True
        direction = "BEARISH"
        signal = "BEARISH_BOS"
        reasons.append("Close broke below latest swing low")

    if structure == "BEARISH" and latest_close is not None and latest_close > last_high:
        choch = True
        direction = "BULLISH"
        signal = "BULLISH_CHOCH"
        reasons.append("Bullish change of character detected")

    elif structure == "BULLISH" and latest_close is not None and latest_close < last_low:
        choch = True
        direction = "BEARISH"
        signal = "BEARISH_CHOCH"
        reasons.append("Bearish change of character detected")

    return {
        "status": "ready",
        "structure": structure,
        "signal": signal,
        "direction": direction,
        "bos": bos,
        "choch": choch,
        "latest_close": latest_close,
        "last_high": last_high,
        "prev_high": prev_high,
        "last_low": last_low,
        "prev_low": prev_low,
        "higher_high": higher_high,
        "higher_low": higher_low,
        "lower_high": lower_high,
        "lower_low": lower_low,
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "reasons": reasons,
    }