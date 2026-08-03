"""TitanAI SK/Fibonacci confluence prototype v2.

This is a transparent research approximation, not a proprietary clone and not
a guarantee of predictive accuracy.
"""

from __future__ import annotations

import pandas as pd


def calculate_sk_features(
    frame: pd.DataFrame,
    *,
    swing_window: int = 5,
) -> pd.DataFrame:
    result = frame.copy()
    high = result["high"]
    low = result["low"]
    close = result["close"]

    result["swing_high"] = high.eq(
        high.rolling(
            swing_window * 2 + 1,
            center=True,
        ).max()
    )
    result["swing_low"] = low.eq(
        low.rolling(
            swing_window * 2 + 1,
            center=True,
        ).min()
    )

    confirmed_high = (
        high.where(result["swing_high"])
        .ffill()
        .shift(swing_window)
    )
    confirmed_low = (
        low.where(result["swing_low"])
        .ffill()
        .shift(swing_window)
    )
    swing_range = (confirmed_high - confirmed_low).abs()

    result["sk_last_swing_high"] = confirmed_high
    result["sk_last_swing_low"] = confirmed_low
    result["sk_swing_range"] = swing_range

    bull_618 = confirmed_high - swing_range * 0.618
    bull_786 = confirmed_high - swing_range * 0.786
    bear_618 = confirmed_low + swing_range * 0.618
    bear_786 = confirmed_low + swing_range * 0.786

    bull_floor = pd.concat(
        [bull_618, bull_786], axis=1
    ).min(axis=1)
    bull_ceiling = pd.concat(
        [bull_618, bull_786], axis=1
    ).max(axis=1)
    bear_floor = pd.concat(
        [bear_618, bear_786], axis=1
    ).min(axis=1)
    bear_ceiling = pd.concat(
        [bear_618, bear_786], axis=1
    ).max(axis=1)

    result["sk_bull_golden_pocket"] = (
        close.between(bull_floor, bull_ceiling)
        & result["htf_proxy_bullish"]
    )
    result["sk_bear_golden_pocket"] = (
        close.between(bear_floor, bear_ceiling)
        & result["htf_proxy_bearish"]
    )

    result["sk_bull_impulse_valid"] = (
        (confirmed_high > confirmed_high.shift(1))
        & (confirmed_low > confirmed_low.shift(1))
    )
    result["sk_bear_impulse_valid"] = (
        (confirmed_high < confirmed_high.shift(1))
        & (confirmed_low < confirmed_low.shift(1))
    )

    result["sk_buy_confirmed"] = (
        result["sk_bull_golden_pocket"]
        & result["sk_bull_impulse_valid"]
        & (result["macd_hist"] > 0)
        & (result["order_flow_delta_proxy"] > 0)
    )
    result["sk_sell_confirmed"] = (
        result["sk_bear_golden_pocket"]
        & result["sk_bear_impulse_valid"]
        & (result["macd_hist"] < 0)
        & (result["order_flow_delta_proxy"] < 0)
    )

    result["sk_bull_invalidation"] = confirmed_low
    result["sk_bear_invalidation"] = confirmed_high
    return result
