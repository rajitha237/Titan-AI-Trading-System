"""
Binance Futures Scanner Service
"""

import httpx

BINANCE_FUTURES_URL = "https://fapi.binance.com/fapi/v1/ticker/24hr"

ALLOWED_CRYPTO_SYMBOLS = {
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
    "DOGEUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT", "LTCUSDT",
    "TRXUSDT", "DOTUSDT", "UNIUSDT", "AAVEUSDT", "NEARUSDT",
    "ARBUSDT", "OPUSDT", "SUIUSDT", "APTUSDT", "FILUSDT",
    "ATOMUSDT", "ETCUSDT", "BCHUSDT", "INJUSDT", "TIAUSDT",
}


async def get_top_futures_symbols(limit: int = 20) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(BINANCE_FUTURES_URL)
        response.raise_for_status()
        data = response.json()

    crypto_pairs = [
        item for item in data
        if item["symbol"] in ALLOWED_CRYPTO_SYMBOLS
    ]

    sorted_pairs = sorted(
        crypto_pairs,
        key=lambda x: float(x["quoteVolume"]),
        reverse=True
    )

    return [
        {
            "symbol": item["symbol"],
            "price": float(item["lastPrice"]),
            "quote_volume": float(item["quoteVolume"]),
            "price_change_percent": float(item["priceChangePercent"]),
        }
        for item in sorted_pairs[:limit]
    ]