"""Market-regime classification for Research Engine v2."""

from __future__ import annotations

import numpy as np
import pandas as pd


def detect_market_regime(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()

    trending = result["adx14"] >= 22
    strong_trending = result["adx14"] >= 28
    high_volatility = result["volatility_regime"] == "HIGH"

    result["market_regime"] = np.select(
        [
            strong_trending
            & high_volatility
            & (result["trend_regime"] == "BULLISH"),
            strong_trending
            & high_volatility
            & (result["trend_regime"] == "BEARISH"),
            trending & (result["trend_regime"] == "BULLISH"),
            trending & (result["trend_regime"] == "BEARISH"),
            ~trending & high_volatility,
        ],
        [
            "BULLISH_EXPANSION",
            "BEARISH_EXPANSION",
            "BULLISH_TREND",
            "BEARISH_TREND",
            "VOLATILE_RANGE",
        ],
        default="QUIET_RANGE",
    )

    result["regime_tradeable"] = result["market_regime"].isin(
        {
            "BULLISH_EXPANSION",
            "BEARISH_EXPANSION",
            "BULLISH_TREND",
            "BEARISH_TREND",
        }
    )
    return result
