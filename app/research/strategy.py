"""Research Engine v2 strict confluence strategy."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class StrategyParameters:
    minimum_score: float = 82.0
    minimum_adx: float = 22.0
    minimum_volume_ratio: float = 1.0
    minimum_abs_delta: float = 0.05
    require_sk: bool = True
    require_bos: bool = False
    allowed_sessions: tuple[str, ...] = (
        "LONDON",
        "NEW_YORK",
    )


def build_strategy_signals(
    features: pd.DataFrame,
    *,
    parameters: StrategyParameters | None = None,
) -> pd.DataFrame:
    parameters = parameters or StrategyParameters()
    frame = features.copy()

    session_ok = frame["session"].isin(
        parameters.allowed_sessions
    )
    trend_strength_ok = frame["adx14"] >= parameters.minimum_adx
    volume_ok = (
        frame["volume_ratio"]
        >= parameters.minimum_volume_ratio
    )
    buy_delta_ok = (
        frame["order_flow_delta_proxy"]
        >= parameters.minimum_abs_delta
    )
    sell_delta_ok = (
        frame["order_flow_delta_proxy"]
        <= -parameters.minimum_abs_delta
    )

    buy_score = (
        (frame["htf_proxy_bullish"]).astype(int) * 20
        + (frame["trend_regime"] == "BULLISH").astype(int) * 15
        + (frame["close"] > frame["vwap"]).astype(int) * 10
        + (frame["macd_hist"] > 0).astype(int) * 10
        + frame["rsi14"].between(45, 66).astype(int) * 10
        + volume_ok.astype(int) * 10
        + buy_delta_ok.astype(int) * 10
        + frame["bullish_bos"].astype(int) * 5
        + frame["sk_buy_confirmed"].astype(int) * 10
    )
    sell_score = (
        (frame["htf_proxy_bearish"]).astype(int) * 20
        + (frame["trend_regime"] == "BEARISH").astype(int) * 15
        + (frame["close"] < frame["vwap"]).astype(int) * 10
        + (frame["macd_hist"] < 0).astype(int) * 10
        + frame["rsi14"].between(34, 55).astype(int) * 10
        + volume_ok.astype(int) * 10
        + sell_delta_ok.astype(int) * 10
        + frame["bearish_bos"].astype(int) * 5
        + frame["sk_sell_confirmed"].astype(int) * 10
    )

    buy_required = (
        session_ok
        & trend_strength_ok
        & frame["regime_tradeable"]
        & frame["htf_proxy_bullish"]
        & buy_delta_ok
    )
    sell_required = (
        session_ok
        & trend_strength_ok
        & frame["regime_tradeable"]
        & frame["htf_proxy_bearish"]
        & sell_delta_ok
    )

    if parameters.require_sk:
        buy_required &= frame["sk_buy_confirmed"]
        sell_required &= frame["sk_sell_confirmed"]

    if parameters.require_bos:
        buy_required &= frame["bullish_bos"]
        sell_required &= frame["bearish_bos"]

    frame["research_buy_score"] = buy_score
    frame["research_sell_score"] = sell_score
    frame["research_score"] = np.maximum(
        buy_score, sell_score
    )

    frame["research_direction"] = np.select(
        [
            buy_required
            & (buy_score >= parameters.minimum_score)
            & (buy_score > sell_score),
            sell_required
            & (sell_score >= parameters.minimum_score)
            & (sell_score > buy_score),
        ],
        ["BUY", "SELL"],
        default="HOLD",
    )
    return frame
