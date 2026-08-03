"""Select the strategy that best matches the live regime and confluence."""
from __future__ import annotations


def select_institutional_strategy(
    *, regime: dict, market_structure: dict | None, fair_value_gaps: dict | None,
    liquidity_sweep: dict | None, vwap: dict | None, order_flow: dict | None,
) -> dict:
    market_structure = market_structure or {}
    fair_value_gaps = fair_value_gaps or {}
    liquidity_sweep = liquidity_sweep or {}
    vwap = vwap or {}
    order_flow = order_flow or {}
    name = str(regime.get("regime", "RANGE"))
    direction = str(regime.get("direction", "NEUTRAL"))
    structure_signal = str(market_structure.get("signal", "NEUTRAL"))
    fvg_signal = str(fair_value_gaps.get("signal", "NEUTRAL"))
    sweep = str(liquidity_sweep.get("direction", "NEUTRAL"))
    flow = str(order_flow.get("pressure", "BALANCED"))
    mean_reversion = bool(vwap.get("mean_reversion_warning"))
    scores = {
        "TREND_CONTINUATION": 0, "PULLBACK_CONTINUATION": 0, "BREAKOUT": 0,
        "LIQUIDITY_SWEEP_REVERSAL": 0, "FVG_CONTINUATION": 0,
        "BOS_CHOCH_REVERSAL": 0, "MEAN_REVERSION": 0, "NO_TRADE": 0,
    }
    reasons=[]
    if not regime.get("tradeable") or direction == "NEUTRAL": scores["NO_TRADE"] += 70
    if "TREND" in name or "EXPANSION" in name: scores["TREND_CONTINUATION"] += 45
    if "EXPANSION" in name: scores["BREAKOUT"] += 25
    if direction == "BUY" and flow == "AGGRESSIVE_BUYERS": scores["TREND_CONTINUATION"] += 20
    if direction == "SELL" and flow == "AGGRESSIVE_SELLERS": scores["TREND_CONTINUATION"] += 20
    if direction == "BUY" and fvg_signal in {"BULLISH_FVG_RETEST", "BULLISH_FVG_NEARBY"}: scores["FVG_CONTINUATION"] += 45
    if direction == "SELL" and fvg_signal in {"BEARISH_FVG_RETEST", "BEARISH_FVG_NEARBY"}: scores["FVG_CONTINUATION"] += 45
    if "RETEST" in fvg_signal: scores["PULLBACK_CONTINUATION"] += 35
    if structure_signal.endswith("BOS"): scores["BREAKOUT"] += 40
    if structure_signal.endswith("CHOCH"): scores["BOS_CHOCH_REVERSAL"] += 50
    if sweep in {"BULLISH", "BEARISH", "BEARISH_WARNING"}: scores["LIQUIDITY_SWEEP_REVERSAL"] += 38
    if name in {"RANGE", "VOLATILE_RANGE"} and mean_reversion: scores["MEAN_REVERSION"] += 50
    selected = max(scores, key=scores.get)
    score = scores[selected]
    if score < 30: selected, score = "NO_TRADE", max(score, 50)
    reasons.append(f"{selected} has the highest regime-fit score")
    return {
        "status":"ready", "selected_strategy":selected,
        "strategy_score":float(score), "direction":direction,
        "eligible":selected != "NO_TRADE", "scores":scores, "reasons":reasons,
    }
