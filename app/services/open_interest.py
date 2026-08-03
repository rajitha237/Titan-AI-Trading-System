"""
Binance Futures Open Interest Service
"""

import httpx

BINANCE_OPEN_INTEREST_URL = "https://fapi.binance.com/fapi/v1/openInterest"


async def get_open_interest(symbol: str = "BTCUSDT") -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            BINANCE_OPEN_INTEREST_URL,
            params={"symbol": symbol},
        )

        response.raise_for_status()
        data = response.json()

    return {
        "symbol": data["symbol"],
        "open_interest": float(data["openInterest"]),
        "time": data["time"],
    }