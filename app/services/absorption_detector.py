"""
TitanAI Absorption Detector v1

Detects possible institutional absorption:
- Aggressive sellers hitting strong bids but price holds
- Aggressive buyers hitting strong asks but price fails to rise
"""


def detect_absorption(
    price: float,
    order_book: dict | None,
    order_flow: dict | None,
    liquidity: dict | None,
    liquidity_trend: dict | None,
) -> dict:
    order_book = order_book or {}
    order_flow = order_flow or {}
    liquidity = liquidity or {}
    liquidity_trend = liquidity_trend or {}

    signal = "NEUTRAL"
    direction = "NONE"
    strength = 0
    reasons = []

    order_book_pressure = order_book.get("pressure")
    order_book_imbalance = float(order_book.get("imbalance") or 0)

    flow_pressure = order_flow.get("pressure")
    delta_ratio = float(order_flow.get("delta_ratio") or 0)

    liquidity_pressure = liquidity.get("pressure")
    liquidity_imbalance = float(liquidity.get("imbalance") or 0)

    liquidity_trend_signal = liquidity_trend.get("signal")
    latest_liquidity_pressure = liquidity_trend.get("latest_pressure")

    # Bullish absorption:
    # Sellers are aggressive, but bid-side liquidity is strong.
    if (
        flow_pressure == "AGGRESSIVE_SELLERS"
        and (
            liquidity_pressure == "BID_LIQUIDITY_STRONG"
            or latest_liquidity_pressure == "BID_LIQUIDITY_STRONG"
            or order_book_pressure == "BUY_PRESSURE"
        )
    ):
        signal = "BUY_ABSORPTION"
        direction = "BULLISH"
        strength += 45
        reasons.append("Aggressive sellers are hitting strong bid liquidity")

        if order_book_imbalance > 0:
            strength += 15
            reasons.append("Order book imbalance still supports buyers")

        if liquidity_imbalance > 0:
            strength += 15
            reasons.append("Liquidity imbalance supports bid side")

        if liquidity_trend_signal in ["BID_ACCUMULATION", "BID_SUPPORT"]:
            strength += 20
            reasons.append("Bid liquidity is accumulating")

    # Bearish absorption:
    # Buyers are aggressive, but ask-side liquidity is strong.
    elif (
        flow_pressure == "AGGRESSIVE_BUYERS"
        and (
            liquidity_pressure == "ASK_LIQUIDITY_STRONG"
            or latest_liquidity_pressure == "ASK_LIQUIDITY_STRONG"
            or order_book_pressure == "SELL_PRESSURE"
        )
    ):
        signal = "SELL_ABSORPTION"
        direction = "BEARISH"
        strength += 45
        reasons.append("Aggressive buyers are hitting strong ask liquidity")

        if order_book_imbalance < 0:
            strength += 15
            reasons.append("Order book imbalance still supports sellers")

        if liquidity_imbalance < 0:
            strength += 15
            reasons.append("Liquidity imbalance supports ask side")

        if liquidity_trend_signal in ["ASK_DISTRIBUTION", "ASK_WALL_REMOVED"]:
            strength += 20
            reasons.append("Ask-side liquidity behaviour is bearish")

    else:
        reasons.append("No clear absorption detected")

    strength = max(0, min(100, strength))

    return {
        "status": "ready",
        "signal": signal,
        "direction": direction,
        "strength": strength,
        "price": price,
        "order_book_pressure": order_book_pressure,
        "order_book_imbalance": order_book_imbalance,
        "order_flow_pressure": flow_pressure,
        "delta_ratio": delta_ratio,
        "liquidity_pressure": liquidity_pressure,
        "liquidity_imbalance": liquidity_imbalance,
        "liquidity_trend_signal": liquidity_trend_signal,
        "reasons": reasons,
    }