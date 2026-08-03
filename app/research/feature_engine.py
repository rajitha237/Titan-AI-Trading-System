"""TitanAI Research Engine v2 feature generation."""

from __future__ import annotations

import numpy as np
import pandas as pd
import ta


def generate_features(candles: pd.DataFrame) -> pd.DataFrame:
    frame = candles.copy()
    if frame.empty:
        return frame

    for column in (
        "open",
        "high",
        "low",
        "close",
        "volume",
        "taker_buy_base",
    ):
        if column in frame:
            frame[column] = pd.to_numeric(
                frame[column], errors="coerce"
            )

    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]

    frame["ema20"] = ta.trend.EMAIndicator(close, 20).ema_indicator()
    frame["ema50"] = ta.trend.EMAIndicator(close, 50).ema_indicator()
    frame["ema100"] = ta.trend.EMAIndicator(close, 100).ema_indicator()
    frame["ema200"] = ta.trend.EMAIndicator(close, 200).ema_indicator()

    frame["rsi14"] = ta.momentum.RSIIndicator(close, 14).rsi()
    frame["adx14"] = ta.trend.ADXIndicator(
        high, low, close, 14
    ).adx()

    macd = ta.trend.MACD(close)
    frame["macd"] = macd.macd()
    frame["macd_signal"] = macd.macd_signal()
    frame["macd_hist"] = macd.macd_diff()

    atr = ta.volatility.AverageTrueRange(high, low, close, 14)
    frame["atr14"] = atr.average_true_range()
    frame["atr_percent"] = (
        frame["atr14"] / close.replace(0, np.nan) * 100
    )

    typical = (high + low + close) / 3.0
    frame["vwap"] = (
        (typical * volume).cumsum()
        / volume.cumsum().replace(0, np.nan)
    )

    frame["volume_sma20"] = volume.rolling(20).mean()
    frame["volume_ratio"] = (
        volume / frame["volume_sma20"].replace(0, np.nan)
    )

    frame["return_1"] = close.pct_change()
    frame["return_5"] = close.pct_change(5)
    frame["return_20"] = close.pct_change(20)
    frame["volatility_20"] = (
        frame["return_1"].rolling(20).std() * 100
    )

    taker_buy = frame.get(
        "taker_buy_base",
        pd.Series(index=frame.index, dtype=float),
    )
    frame["taker_buy_ratio"] = (
        taker_buy / volume.replace(0, np.nan)
    )
    frame["order_flow_delta_proxy"] = (
        frame["taker_buy_ratio"] * 2.0 - 1.0
    )

    frame["rolling_high_20"] = high.shift(1).rolling(20).max()
    frame["rolling_low_20"] = low.shift(1).rolling(20).min()
    frame["rolling_high_50"] = high.shift(1).rolling(50).max()
    frame["rolling_low_50"] = low.shift(1).rolling(50).min()

    frame["bullish_bos"] = close > frame["rolling_high_20"]
    frame["bearish_bos"] = close < frame["rolling_low_20"]

    frame["ema_slope_20"] = frame["ema20"].pct_change(5) * 100
    frame["ema_slope_50"] = frame["ema50"].pct_change(10) * 100

    frame["trend_regime"] = np.select(
        [
            (
                (frame["ema20"] > frame["ema50"])
                & (frame["ema50"] > frame["ema100"])
                & (frame["ema100"] > frame["ema200"])
            ),
            (
                (frame["ema20"] < frame["ema50"])
                & (frame["ema50"] < frame["ema100"])
                & (frame["ema100"] < frame["ema200"])
            ),
        ],
        ["BULLISH", "BEARISH"],
        default="RANGING",
    )

    median_atr = frame["atr_percent"].rolling(100).median()
    frame["volatility_regime"] = np.where(
        frame["atr_percent"] > median_atr,
        "HIGH",
        "LOW",
    )

    if "open_time" in frame:
        times = pd.to_datetime(
            frame["open_time"], utc=True, errors="coerce"
        )
        hours = times.dt.hour
        frame["session"] = np.select(
            [
                hours.between(0, 7),
                hours.between(8, 12),
                hours.between(13, 20),
            ],
            ["ASIA", "LONDON", "NEW_YORK"],
            default="LATE_US",
        )
    else:
        frame["session"] = "UNKNOWN"

    frame["htf_proxy_bullish"] = (
        (frame["ema50"] > frame["ema200"])
        & (frame["ema_slope_50"] > 0)
    )
    frame["htf_proxy_bearish"] = (
        (frame["ema50"] < frame["ema200"])
        & (frame["ema_slope_50"] < 0)
    )

    return frame
