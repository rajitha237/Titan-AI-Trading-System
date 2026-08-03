"""
Binance Futures Funding Rate Service
"""

import httpx

BINANCE_PREMIUM_INDEX_URL = "https://fapi.binance.com/fapi/v1/premiumIndex"


async def get_funding_rate(symbol: str = "BTCUSDT") -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            BINANCE_PREMIUM_INDEX_URL,
            params={"symbol": symbol},
        )

        response.raise_for_status()
        data = response.json()

    return {
        "symbol": data["symbol"],
        "mark_price": float(data["markPrice"]),
        "index_price": float(data["indexPrice"]),
        "last_funding_rate": float(data["lastFundingRate"]),
        "next_funding_time": data["nextFundingTime"],
    }