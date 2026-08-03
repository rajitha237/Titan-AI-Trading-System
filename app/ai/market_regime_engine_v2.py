"""TitanAI institutional live market-regime engine v2."""

from __future__ import annotations
from typing import Any


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return default if number != number or number in (float("inf"), float("-inf")) else number
    except (TypeError, ValueError):
        return default


def classify_live_market_regime(
    *,
    technical: dict | None,
    multi_timeframe: dict | None,
    market_structure: dict | None,
    vwap: dict | None,
    volume_profile: dict | None,
    order_flow: dict | None,
    liquidity_sweep: dict | None,
) -> dict:
    technical = technical or {}
    multi_timeframe = multi_timeframe or {}
    market_structure = market_structure or {}
    vwap = vwap or {}
    volume_profile = volume_profile or {}
    order_flow = order_flow or {}
    liquidity_sweep = liquidity_sweep or {}

    trend = str(technical.get("trend", "UNKNOWN")).upper()
    mtf = str(
        multi_timeframe.get("trend")
        or multi_timeframe.get("signal")
        or multi_timeframe.get("direction")
        or "UNKNOWN"
    ).upper()
    structure = str(market_structure.get("structure", "UNKNOWN")).upper()
    structure_signal = str(market_structure.get("signal", "NEUTRAL")).upper()
    flow = str(order_flow.get("pressure", "BALANCED")).upper()
    vwap_bias = str(vwap.get("bias") or vwap.get("signal") or "NEUTRAL").upper()
    vwap_trend = str(vwap.get("vwap_trend") or vwap.get("trend") or "FLAT").upper()
    profile = str(volume_profile.get("signal") or volume_profile.get("bias") or "NEUTRAL").upper()
    sweep = str(liquidity_sweep.get("direction") or "NEUTRAL").upper()

    atr_percent = _f(technical.get("atr_percent"), 0.0)
    adx = _f(technical.get("adx") or technical.get("adx14"), 0.0)
    volume_ratio = _f(technical.get("volume_ratio"), 1.0)

    bull = 0.0
    bear = 0.0
    reasons: list[str] = []

    if trend == "BULLISH": bull += 18
    elif trend == "BEARISH": bear += 18
    if "BULL" in mtf: bull += 22
    elif "BEAR" in mtf: bear += 22
    if structure == "BULLISH": bull += 16
    elif structure == "BEARISH": bear += 16
    if structure_signal in {"BULLISH_BOS", "BULLISH_CHOCH"}: bull += 12
    elif structure_signal in {"BEARISH_BOS", "BEARISH_CHOCH"}: bear += 12
    if flow == "AGGRESSIVE_BUYERS": bull += 12
    elif flow == "AGGRESSIVE_SELLERS": bear += 12
    if "ABOVE" in vwap_bias or vwap_bias == "BULLISH": bull += 8
    elif "BELOW" in vwap_bias or vwap_bias == "BEARISH": bear += 8
    if vwap_trend == "RISING": bull += 5
    elif vwap_trend == "FALLING": bear += 5
    if profile == "BULLISH": bull += 4
    elif profile == "BEARISH": bear += 4
    if sweep == "BULLISH": bull += 3
    elif sweep.startswith("BEARISH"): bear += 3

    strength = max(bull, bear)
    conflict = min(bull, bear)
    directional_gap = abs(bull - bear)
    high_volatility = atr_percent >= 1.2
    strong_trend = adx >= 25 or strength >= 55
    compressed = atr_percent > 0 and atr_percent < 0.45 and volume_ratio < 0.9

    if compressed:
        regime = "COMPRESSION"
        direction = "NEUTRAL"
        tradeable = False
        reasons.append("Volatility and volume are compressed")
    elif directional_gap < 12 or conflict >= 28:
        regime = "VOLATILE_RANGE" if high_volatility else "RANGE"
        direction = "NEUTRAL"
        tradeable = False
        reasons.append("Directional evidence is conflicting")
    elif bull > bear:
        direction = "BUY"
        regime = "BULLISH_EXPANSION" if high_volatility and strong_trend else "BULLISH_TREND"
        tradeable = strong_trend
        reasons.append("Bullish live layers dominate")
    else:
        direction = "SELL"
        regime = "BEARISH_EXPANSION" if high_volatility and strong_trend else "BEARISH_TREND"
        tradeable = strong_trend
        reasons.append("Bearish live layers dominate")

    confidence = max(0.0, min(100.0, directional_gap + strength * 0.35 - conflict * 0.25))
    return {
        "status": "ready",
        "version": "2.0",
        "regime": regime,
        "direction": direction,
        "tradeable": tradeable,
        "confidence": round(confidence, 2),
        "bullish_evidence": round(bull, 2),
        "bearish_evidence": round(bear, 2),
        "directional_gap": round(directional_gap, 2),
        "high_volatility": high_volatility,
        "strong_trend": strong_trend,
        "inputs": {"atr_percent": atr_percent, "adx": adx, "volume_ratio": volume_ratio},
        "reasons": reasons,
    }
