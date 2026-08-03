"""Safe interval scheduling helpers."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

MINIMUM_INTERVAL_SECONDS = 30.0
DEFAULT_INTERVAL_SECONDS = 60.0


def normalize_interval(
    interval_seconds: float,
) -> float:
    """Enforce a conservative minimum cycle interval."""
    try:
        interval = float(interval_seconds)
    except (TypeError, ValueError):
        interval = DEFAULT_INTERVAL_SECONDS

    if interval != interval:
        interval = DEFAULT_INTERVAL_SECONDS

    return max(
        MINIMUM_INTERVAL_SECONDS,
        interval,
    )


def next_run_time(
    *,
    interval_seconds: float,
    now: datetime | None = None,
) -> datetime:
    current = now or datetime.now(timezone.utc)

    return current + timedelta(
        seconds=normalize_interval(
            interval_seconds
        )
    )


async def sleep_until_next_cycle(
    *,
    interval_seconds: float,
    shutdown_event: asyncio.Event,
) -> bool:
    """Sleep until the next cycle or return early on shutdown.

    Returns True when shutdown was requested during the wait.
    """
    interval = normalize_interval(
        interval_seconds
    )

    try:
        await asyncio.wait_for(
            shutdown_event.wait(),
            timeout=interval,
        )
        return True

    except asyncio.TimeoutError:
        return False
