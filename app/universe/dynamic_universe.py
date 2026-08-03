"""
TitanAI Dynamic Universe Engine
"""

from app.services.futures_scanner import get_top_futures_symbols


async def get_dynamic_trade_universe(limit: int = 20) -> list[str]:
    """
    Build a dynamic trading universe from Binance Futures.
    """

    top_symbols = await get_top_futures_symbols(limit=limit)

    return [
        item["symbol"]
        for item in top_symbols
    ]