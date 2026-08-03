"""Chronological train/validation/test splitting."""

from __future__ import annotations

import pandas as pd


def chronological_split(
    frame: pd.DataFrame,
    *,
    train_fraction: float = 0.60,
    validation_fraction: float = 0.20,
) -> dict[str, pd.DataFrame]:
    if frame.empty:
        return {
            "train": frame.copy(),
            "validation": frame.copy(),
            "test": frame.copy(),
        }

    train_fraction = min(max(train_fraction, 0.4), 0.8)
    validation_fraction = min(
        max(validation_fraction, 0.1), 0.3
    )
    if train_fraction + validation_fraction >= 0.95:
        validation_fraction = 0.95 - train_fraction

    total = len(frame)
    train_end = max(1, int(total * train_fraction))
    validation_end = max(
        train_end + 1,
        int(total * (train_fraction + validation_fraction)),
    )

    return {
        "train": frame.iloc[:train_end].copy(),
        "validation": frame.iloc[
            train_end:validation_end
        ].copy(),
        "test": frame.iloc[validation_end:].copy(),
    }
