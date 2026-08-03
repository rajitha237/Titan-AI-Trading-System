"""
TitanAI Multi-Timeframe Analysis Engine
"""

from app.services.candles import get_klines
from app.ai.technical_engine import analyze_technical


async def analyze_multi_timeframe(symbol: str = "BTCUSDT") -> dict:
    timeframes = ["5m", "15m", "1h", "4h"]
    results = {}

    bullish_count = 0
    bearish_count = 0

    for timeframe in timeframes:
        candles = await get_klines(symbol, timeframe, 150)
        analysis = analyze_technical(candles)

        results[timeframe] = analysis

        if analysis["trend"] == "BULLISH":
            bullish_count += 1
        elif analysis["trend"] == "BEARISH":
            bearish_count += 1

    if bullish_count >= 3:
        overall_trend = "BULLISH"
    elif bearish_count >= 3:
        overall_trend = "BEARISH"
    else:
        overall_trend = "MIXED"

    return {
        "symbol": symbol,
        "timeframes": results,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "overall_trend": overall_trend,
    }