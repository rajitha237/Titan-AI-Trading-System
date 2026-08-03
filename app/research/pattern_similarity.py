"""Historical feature-vector similarity lookup v2.1."""

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

    if (
        row_index <= 0
        or row_index >= len(frame) - forward_bars
    ):
        return {
            "status": "invalid_index",
            "sample_size": 0,
        }

    # Force all similarity features to real float64 values. Pandas 3 can keep
    # mixed/object dtypes after arithmetic, which makes NumPy's sqrt ufunc fail.
    numeric = frame.loc[:, columns].apply(
        pd.to_numeric,
        errors="coerce",
    ).astype("float64")

    numeric = numeric.replace(
        [np.inf, -np.inf],
        np.nan,
    )

    history = numeric.iloc[:row_index].copy()
    target = numeric.iloc[row_index].copy()

    means = history.mean(numeric_only=True)
    stds = history.std(numeric_only=True).replace(
        0.0,
        np.nan,
    )

    normalized = (
        (history - means) / stds
    ).astype("float64")

    target_vector = (
        (target - means) / stds
    ).astype("float64")

    valid = normalized.dropna(axis=0, how="any")

    if valid.empty or target_vector.isna().any():
        return {
            "status": "insufficient_clean_data",
            "sample_size": 0,
        }

    matrix_values = valid.to_numpy(
        dtype=np.float64,
        copy=False,
    )
    target_values = target_vector.to_numpy(
        dtype=np.float64,
        copy=False,
    )

    squared_distance = np.square(
        matrix_values - target_values
    )
    distances_array = np.sqrt(
        np.mean(squared_distance, axis=1)
    )

    distances = pd.Series(
        distances_array,
        index=valid.index,
        dtype="float64",
    )

    nearest = distances.nsmallest(
        max(1, min(int(top_k), len(distances)))
    )

    closes = pd.to_numeric(
        frame["close"],
        errors="coerce",
    ).astype("float64")

    forward_returns: list[float] = []

    for label_index in nearest.index:
        # The feature frame normally has a RangeIndex, but using get_loc keeps
        # this correct even if the caller passes a filtered/non-default index.
        location = frame.index.get_loc(label_index)

        if isinstance(location, slice):
            location = location.start
        elif not isinstance(location, (int, np.integer)):
            matches = np.flatnonzero(location)
            if len(matches) == 0:
                continue
            location = int(matches[0])

        forward_location = int(location) + int(forward_bars)

        if forward_location >= len(frame):
            continue

        start = float(closes.iloc[int(location)])
        finish = float(closes.iloc[forward_location])

        if (
            np.isfinite(start)
            and np.isfinite(finish)
            and start > 0
        ):
            forward_returns.append(
                (finish / start - 1.0) * 100.0
            )

    if not forward_returns:
        return {
            "status": "no_forward_samples",
            "sample_size": 0,
        }

    returns_array = np.asarray(
        forward_returns,
        dtype=np.float64,
    )

    return {
        "status": "ready",
        "sample_size": int(len(returns_array)),
        "positive_probability_percent": float(
            np.mean(returns_array > 0) * 100.0
        ),
        "average_forward_return_percent": float(
            np.mean(returns_array)
        ),
        "median_forward_return_percent": float(
            np.median(returns_array)
        ),
        "average_similarity_distance": float(
            nearest.mean()
        ),
        "feature_count": len(columns),
        "forward_bars": int(forward_bars),
    }
