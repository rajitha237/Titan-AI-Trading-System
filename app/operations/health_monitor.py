"""TitanAI Operations Health Monitor v35.1.

Read-only operational diagnostics for the local TitanAI process and its
persistent stores. This module never submits, cancels, or modifies exchange
orders.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from app.monitoring.exchange_health_monitor import (
    check_exchange_health,
)
from app.service.service_state_manager import (
    build_service_state_snapshot,
)


APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"


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


def _read_process_memory_mb() -> float:
    """Return resident memory in MB when the platform exposes it."""
    try:
        import resource

        usage = resource.getrusage(
            resource.RUSAGE_SELF
        ).ru_maxrss

        # macOS reports bytes; Linux commonly reports KiB.
        if os.uname().sysname == "Darwin":
            return usage / (1024.0 * 1024.0)

        return usage / 1024.0

    except Exception:
        return 0.0


def _check_database(
    path: Path,
) -> dict:
    if not path.exists():
        return {
            "status": "missing",
            "available": False,
            "path": str(path),
            "error": None,
        }

    try:
        connection = sqlite3.connect(
            path,
            timeout=3.0,
        )

        try:
            connection.execute(
                "PRAGMA quick_check"
            ).fetchone()
        finally:
            connection.close()

        return {
            "status": "healthy",
            "available": True,
            "path": str(path),
            "error": None,
        }

    except Exception as error:
        return {
            "status": "error",
            "available": False,
            "path": str(path),
            "error": str(error),
        }


def check_operations_health(
    *,
    exchange_health_function: Callable[
        [],
        dict,
    ] = check_exchange_health,
    service_state_function: Callable[
        [],
        dict,
    ] = build_service_state_snapshot,
    disk_usage_function: Callable = (
        shutil.disk_usage
    ),
    memory_function: Callable[
        [],
        float,
    ] = _read_process_memory_mb,
    maximum_memory_mb: float = 1024.0,
    minimum_free_disk_percent: float = 10.0,
) -> dict:
    """Build one read-only operational health report."""
    started = time.perf_counter()
    warnings: list[str] = []
    errors: list[str] = []

    try:
        exchange_health = (
            exchange_health_function()
        )
        if not isinstance(
            exchange_health,
            dict,
        ):
            raise RuntimeError(
                "Exchange health response "
                "was not a dictionary"
            )
    except Exception as error:
        exchange_health = {
            "status": "degraded",
            "healthy": False,
            "errors": [str(error)],
        }
        errors.append(
            f"Exchange health check failed: "
            f"{error}"
        )

    try:
        service_state = (
            service_state_function()
        )
        if not isinstance(
            service_state,
            dict,
        ):
            raise RuntimeError(
                "Service state response "
                "was not a dictionary"
            )
    except Exception as error:
        service_state = {
            "status": "error",
            "latest_heartbeat": None,
        }
        errors.append(
            f"Service state check failed: "
            f"{error}"
        )

    try:
        disk_usage = disk_usage_function(
            APP_ROOT
        )
        total_bytes = float(
            disk_usage.total
        )
        free_bytes = float(
            disk_usage.free
        )
        free_percent = (
            free_bytes / total_bytes * 100.0
            if total_bytes > 0
            else 0.0
        )
    except Exception as error:
        total_bytes = 0.0
        free_bytes = 0.0
        free_percent = 0.0
        errors.append(
            f"Disk health check failed: "
            f"{error}"
        )

    memory_mb = _safe_float(
        memory_function()
    )

    if (
        memory_mb
        > max(
            1.0,
            maximum_memory_mb,
        )
    ):
        warnings.append(
            "Process memory usage exceeded "
            "the configured warning limit"
        )

    if (
        free_percent
        < max(
            0.0,
            minimum_free_disk_percent,
        )
    ):
        errors.append(
            "Free disk space is below "
            "the configured safety minimum"
        )

    database_paths = [
        DATA_DIR
        / "titanai_service_state.db",
        DATA_DIR
        / "titanai_order_recovery.db",
        DATA_DIR
        / "titanai_notifications.db",
        DATA_DIR
        / "titanai_performance.db",
    ]

    databases = [
        _check_database(path)
        for path in database_paths
    ]

    failed_databases = [
        database
        for database in databases
        if database["status"]
        == "error"
    ]

    missing_databases = [
        database
        for database in databases
        if database["status"]
        == "missing"
    ]

    if failed_databases:
        errors.append(
            "One or more persistent databases "
            "failed their integrity check"
        )

    if missing_databases:
        warnings.append(
            "One or more optional persistent "
            "databases have not been created yet"
        )

    exchange_healthy = (
        exchange_health.get("healthy")
        is True
    )

    if not exchange_healthy:
        errors.append(
            "Exchange health is degraded"
        )

    if errors:
        overall_status = "CRITICAL"
    elif warnings:
        overall_status = "WARNING"
    else:
        overall_status = "HEALTHY"

    elapsed_ms = (
        time.perf_counter() - started
    ) * 1000.0

    return {
        "status": overall_status,
        "version": "v35.1",
        "healthy": (
            overall_status == "HEALTHY"
        ),
        "checked_at": _utc_now(),
        "check_duration_ms": round(
            elapsed_ms,
            3,
        ),
        "exchange": exchange_health,
        "service": service_state,
        "resources": {
            "memory_mb": round(
                memory_mb,
                3,
            ),
            "maximum_memory_mb": (
                maximum_memory_mb
            ),
            "disk_total_bytes": int(
                total_bytes
            ),
            "disk_free_bytes": int(
                free_bytes
            ),
            "disk_free_percent": round(
                free_percent,
                3,
            ),
            "minimum_free_disk_percent": (
                minimum_free_disk_percent
            ),
        },
        "databases": databases,
        "warnings": list(
            dict.fromkeys(warnings)
        ),
        "errors": list(
            dict.fromkeys(errors)
        ),
        "read_only": True,
    }
