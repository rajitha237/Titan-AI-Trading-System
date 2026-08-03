"""Shared synthetic fixtures for TitanAI tests."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd


def make_candles(rows: int = 600) -> pd.DataFrame:
    """Create deterministic Binance-like candles for offline tests."""
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    index = np.arange(rows, dtype=float)

    trend = 100.0 + index * 0.035
    cycle = np.sin(index / 11.0) * 1.8
    close = trend + cycle
    open_ = close - np.sin(index / 5.0) * 0.25
    high = np.maximum(open_, close) + 0.45
    low = np.minimum(open_, close) - 0.45
    volume = 1000.0 + np.cos(index / 7.0) * 160.0 + index * 0.2
    taker_buy = volume * (0.52 + np.sin(index / 9.0) * 0.08)

    open_times = [start + timedelta(minutes=15 * int(i)) for i in index]
    close_times = [value + timedelta(minutes=15) for value in open_times]

    return pd.DataFrame(
        {
            "open_time": open_times,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "close_time": close_times,
            "quote_asset_volume": volume * close,
            "number_of_trades": 100 + (index % 30),
            "taker_buy_base": taker_buy,
            "taker_buy_quote": taker_buy * close,
            "ignore": 0,
            "symbol": "BTCUSDT",
            "timeframe": "15m",
        }
    )


def finite_number(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
