"""
Binance Candlestick / Kline Service
"""

import httpx

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"


async def get_klines(
    symbol: str = "BTCUSDT",
    interval: str = "15m",
    limit: int = 100,
):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            BINANCE_KLINES_URL,
            params={
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            },
        )
        response.raise_for_status()
        return response.json()


def normalize_klines(klines: list) -> list[dict]:
    return [
        {
            "time": int(item[0] / 1000),
            "open": float(item[1]),
            "high": float(item[2]),
            "low": float(item[3]),
            "close": float(item[4]),
            "volume": float(item[5]),
        }
        for item in klines
    ]