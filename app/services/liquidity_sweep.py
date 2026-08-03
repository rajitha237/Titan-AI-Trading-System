"""
TitanAI Liquidity Sweep / Stop Hunt Detector v1
"""

def detect_liquidity_sweep(
    price: float,
    liquidity: dict | None,
    liquidity_trend: dict | None,
    order_flow: dict | None,
) -> dict:
    liquidity = liquidity or {}
    liquidity_trend = liquidity_trend or {}
    order_flow = order_flow or {}

    signal = "NEUTRAL"
    direction = "NONE"
    confidence = 0
    reasons = []

    liquidity_signal = liquidity_trend.get("signal")
    latest_pressure = liquidity_trend.get("latest_pressure")
    flow_pressure = order_flow.get("pressure")
    delta_ratio = order_flow.get("delta_ratio", 0) or 0

    bid_walls = liquidity.get("bid_walls", [])
    ask_walls = liquidity.get("ask_walls", [])

    bid_removed = liquidity_signal == "BID_WALL_REMOVED"
    ask_removed = liquidity_signal == "ASK_WALL_REMOVED"

    if ask_removed and flow_pressure != "AGGRESSIVE_SELLERS":
        signal = "BUY_SIDE_SWEEP"
        direction = "BULLISH"
        confidence += 45
        reasons.append("Ask liquidity wall removed")

        if flow_pressure in ["AGGRESSIVE_BUYERS", "BALANCED"]:
            confidence += 25
            reasons.append("Order flow does not confirm heavy selling")

        if delta_ratio >= 0:
            confidence += 15
            reasons.append("Delta supports upside continuation")

    elif bid_removed and flow_pressure != "AGGRESSIVE_BUYERS":
        signal = "SELL_SIDE_SWEEP"
        direction = "BEARISH"
        confidence += 45
        reasons.append("Bid liquidity wall removed")

        if flow_pressure in ["AGGRESSIVE_SELLERS", "BALANCED"]:
            confidence += 25
            reasons.append("Order flow does not confirm heavy buying")

        if delta_ratio <= 0:
            confidence += 15
            reasons.append("Delta supports downside continuation")

    elif latest_pressure == "BID_LIQUIDITY_STRONG" and flow_pressure == "AGGRESSIVE_SELLERS":
        signal = "SELL_ABSORPTION_WARNING"
        direction = "BULLISH_WARNING"
        confidence = 65
        reasons.append("Aggressive sellers hitting strong bid liquidity")

    elif latest_pressure == "ASK_LIQUIDITY_STRONG" and flow_pressure == "AGGRESSIVE_BUYERS":
        signal = "BUY_ABSORPTION_WARNING"
        direction = "BEARISH_WARNING"
        confidence = 65
        reasons.append("Aggressive buyers hitting strong ask liquidity")

    else:
        reasons.append("No liquidity sweep detected")

    confidence = max(0, min(100, confidence))

    return {
        "status": "ready",
        "signal": signal,
        "direction": direction,
        "confidence": confidence,
        "bid_removed": bid_removed,
        "ask_removed": ask_removed,
        "bid_wall_count": len(bid_walls),
        "ask_wall_count": len(ask_walls),
        "price": price,
        "reasons": reasons,
    }