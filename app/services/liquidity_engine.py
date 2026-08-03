"""
TitanAI Liquidity Engine v1

Detects liquidity walls and liquidity imbalance from order book depth.
"""


def analyze_liquidity(order_book: dict) -> dict:
    bids = order_book.get("bids", [])
    asks = order_book.get("asks", [])

    bid_liquidity = 0.0
    ask_liquidity = 0.0

    bid_walls = []
    ask_walls = []

    for price, qty in bids[:20]:
        value = float(price) * float(qty)
        bid_liquidity += value

        if value >= 50_000:
            bid_walls.append({
                "price": float(price),
                "qty": float(qty),
                "value": round(value, 2),
            })

    for price, qty in asks[:20]:
        value = float(price) * float(qty)
        ask_liquidity += value

        if value >= 50_000:
            ask_walls.append({
                "price": float(price),
                "qty": float(qty),
                "value": round(value, 2),
            })

    total = bid_liquidity + ask_liquidity
    imbalance = (
        (bid_liquidity - ask_liquidity) / total
        if total else 0
    )

    if imbalance > 0.15:
        pressure = "BID_LIQUIDITY_STRONG"
    elif imbalance < -0.15:
        pressure = "ASK_LIQUIDITY_STRONG"
    else:
        pressure = "BALANCED_LIQUIDITY"

    return {
        "bid_liquidity": round(bid_liquidity, 2),
        "ask_liquidity": round(ask_liquidity, 2),
        "imbalance": round(imbalance, 4),
        "pressure": pressure,
        "bid_walls": bid_walls[:5],
        "ask_walls": ask_walls[:5],
    }
