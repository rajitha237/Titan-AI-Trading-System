"""
TitanAI Technical Analysis Engine
"""

import pandas as pd
import ta


def analyze_technical(klines: list) -> dict:
    """
    Analyze Binance candlestick data using technical indicators.
    """

    df = pd.DataFrame(
        klines,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_asset_volume",
            "number_of_trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )

    # Convert numeric columns
    numeric_cols = ["open", "high", "low", "close", "volume"]

    for col in numeric_cols:
        df[col] = df[col].astype(float)

    # Indicators
    df["ema20"] = ta.trend.EMAIndicator(
        close=df["close"],
        window=20,
    ).ema_indicator()

    df["ema50"] = ta.trend.EMAIndicator(
        close=df["close"],
        window=50,
    ).ema_indicator()

    df["rsi"] = ta.momentum.RSIIndicator(
        close=df["close"],
        window=14,
    ).rsi()

    macd = ta.trend.MACD(close=df["close"])

    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    latest = df.iloc[-1]

    trend = (
        "BULLISH"
        if latest["ema20"] > latest["ema50"]
        else "BEARISH"
    )

    if latest["rsi"] < 30:
        rsi_signal = "OVERSOLD"
    elif latest["rsi"] > 70:
        rsi_signal = "OVERBOUGHT"
    else:
        rsi_signal = "NEUTRAL"

    macd_signal = (
        "BUY"
        if latest["macd"] > latest["macd_signal"]
        else "SELL"
    )

    return {
        "trend": trend,
        "ema20": round(float(latest["ema20"]), 2),
        "ema50": round(float(latest["ema50"]), 2),
        "rsi": round(float(latest["rsi"]), 2),
        "rsi_signal": rsi_signal,
        "macd": round(float(latest["macd"]), 4),
        "macd_signal": round(float(latest["macd_signal"]), 4),
        "macd_direction": macd_signal,
    }