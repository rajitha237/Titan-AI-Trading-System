"""TitanAI Exchange Health Monitor v29.

Read-only Binance Testnet health checks. This module never submits, cancels,
or modifies orders.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.exchange.binance_testnet_client import (
    get_server_time,
    get_time_sync_status,
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
        if (
            number != number
            or number in {
                float("inf"),
                float("-inf"),
            }
        ):
            return default
        return number
    except (TypeError, ValueError):
        return default


def check_exchange_health(
    *,
    server_time_function: Callable[[], int] = get_server_time,
    time_sync_status_function: Callable[[], dict] = get_time_sync_status,
    maximum_latency_ms: float = 2500.0,
    maximum_clock_offset_ms: float = 5000.0,
) -> dict:
    """Return a bounded read-only exchange health snapshot."""
    started = time.perf_counter()
    errors: list[str] = []

    try:
        server_time_ms = int(
            server_time_function()
        )
    except Exception as error:
        server_time_ms = 0
        errors.append(
            f"Server-time query failed: {error}"
        )

    latency_ms = (
        time.perf_counter() - started
    ) * 1000.0

    try:
        sync_status = (
            time_sync_status_function()
        )
        if not isinstance(
            sync_status,
            dict,
        ):
            raise RuntimeError(
                "Time-sync status was not a dictionary"
            )
    except Exception as error:
        sync_status = {}
        errors.append(
            f"Time-sync diagnostics failed: {error}"
        )

    offset_ms = abs(
        _safe_float(
            sync_status.get("offset_ms"),
            0.0,
        )
    )

    checks = {
        "server_reachable": (
            server_time_ms > 0
        ),
        "latency_within_limit": (
            latency_ms
            <= max(
                1.0,
                maximum_latency_ms,
            )
        ),
        "clock_offset_within_limit": (
            offset_ms
            <= max(
                0.0,
                maximum_clock_offset_ms,
            )
        ),
    }

    healthy = (
        not errors
        and all(checks.values())
    )

    return {
        "status": (
            "healthy"
            if healthy
            else "degraded"
        ),
        "version": "v29",
        "healthy": healthy,
        "checked_at": _utc_now(),
        "server_time_ms": server_time_ms,
        "latency_ms": round(
            latency_ms,
            3,
        ),
        "clock_offset_ms": round(
            offset_ms,
            3,
        ),
        "maximum_latency_ms": (
            maximum_latency_ms
        ),
        "maximum_clock_offset_ms": (
            maximum_clock_offset_ms
        ),
        "checks": checks,
        "errors": errors,
        "read_only": True,
    }
