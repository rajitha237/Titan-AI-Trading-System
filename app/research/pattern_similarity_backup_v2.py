"""Historical feature-vector similarity lookup."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


DEFAULT_FEATURES = (
    "rsi14",
    "adx14",
    "atr_percent",
    "volume_ratio",
    "order_flow_delta_proxy",
    "ema_slope_20",
    "ema_slope_50",
    "macd_hist",
    "return_5",
    "volatility_20",
)


def find_similar_patterns(
    frame: pd.DataFrame,
    *,
    row_index: int | None = None,
    feature_columns: Iterable[str] = DEFAULT_FEATURES,
    forward_bars: int = 12,
    top_k: int = 100,
) -> dict:
    columns = [
        column
        for column in feature_columns
        if column in frame.columns
    ]
    if not columns or len(frame) <= forward_bars + 50:
        return {
            "status": "insufficient_data",
            "sample_size": 0,
        }

    row_index = (
        len(frame) - forward_bars - 1
        if row_index is None
        else int(row_index)
    )
    if row_index <= 0 or row_index >= len(frame) - forward_bars:
        return {
            "status": "invalid_index",
            "sample_size": 0,
        }

    history = frame.iloc[:row_index].copy()
    target = frame.iloc[row_index]

    matrix = history[columns].replace(
        [np.inf, -np.inf], np.nan
    )
    means = matrix.mean()
    stds = matrix.std().replace(0, np.nan)
    normalized = (matrix - means) / stds
    target_vector = (target[columns] - means) / stds

    valid = normalized.dropna()
    if valid.empty or target_vector.isna().any():
        return {
            "status": "insufficient_clean_data",
            "sample_size": 0,
        }

    distances = np.sqrt(
        ((valid - target_vector) ** 2).mean(axis=1)
    )
    nearest = distances.nsmallest(
        max(1, min(top_k, len(distances)))
    )

    returns = []
    for index in nearest.index:
        if index + forward_bars >= len(frame):
            continue
        start = float(frame.iloc[index]["close"])
        finish = float(
            frame.iloc[index + forward_bars]["close"]
        )
        if start > 0:
            returns.append((finish / start - 1.0) * 100)

    if not returns:
        return {
            "status": "no_forward_samples",
            "sample_size": 0,
        }

    positive = [value for value in returns if value > 0]
    return {
        "status": "ready",
        "sample_size": len(returns),
        "positive_probability_percent": (
            len(positive) / len(returns) * 100
        ),
        "average_forward_return_percent": float(
            np.mean(returns)
        ),
        "median_forward_return_percent": float(
            np.median(returns)
        ),
        "average_similarity_distance": float(
            nearest.mean()
        ),
    }
