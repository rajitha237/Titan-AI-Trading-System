"""
Binance Order Book Service
"""

import httpx

BINANCE_DEPTH_URL = "https://api.binance.com/api/v3/depth"


async def get_order_book(symbol: str = "BTCUSDT", limit: int = 100):
    """
    Fetch Binance Order Book.
    """

    async with httpx.AsyncClient() as client:

        response = await client.get(
            BINANCE_DEPTH_URL,
            params={
                "symbol": symbol,
                "limit": limit,
            },
        )

        response.raise_for_status()

        return response.json()


def analyze_order_book(order_book: dict) -> dict:
    """
    Analyze Binance order book.

    Returns:
        - Buy Volume
        - Sell Volume
        - Imbalance Score
        - Market Pressure
    """

    bids = order_book.get("bids", [])
    asks = order_book.get("asks", [])

    buy_volume = sum(
        float(price) * float(quantity)
        for price, quantity in bids
    )

    sell_volume = sum(
        float(price) * float(quantity)
        for price, quantity in asks
    )

    total_volume = buy_volume + sell_volume

    if total_volume == 0:
        imbalance = 0
    else:
        imbalance = (buy_volume - sell_volume) / total_volume

    if imbalance > 0.15:
        pressure = "BUY_PRESSURE"
    elif imbalance < -0.15:
        pressure = "SELL_PRESSURE"
    else:
        pressure = "NEUTRAL"

    return {
        "buy_volume": round(buy_volume, 2),
        "sell_volume": round(sell_volume, 2),
        "imbalance": round(imbalance, 4),
        "pressure": pressure,
    }