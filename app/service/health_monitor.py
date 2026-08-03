"""Health evaluation for autonomous testnet cycles."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def evaluate_service_health(
    *,
    result: dict | None,
    consecutive_errors: int,
    maximum_consecutive_errors: int,
) -> dict:
    """Classify service health without changing runner decisions."""
    result = _mapping(result)
    execution = _mapping(
        result.get("execution")
    )

    status = str(
        result.get("status", "unknown")
    ).lower()
    submitted = bool(
        execution.get("submitted", False)
    )

    issues: list[str] = []

    if status == "error":
        issues.append(
            "Latest runner cycle returned error"
        )

    if consecutive_errors > 0:
        issues.append(
            f"Consecutive cycle errors: "
            f"{consecutive_errors}"
        )

    if (
        consecutive_errors
        >= maximum_consecutive_errors
    ):
        health = "CRITICAL"
    elif issues:
        health = "DEGRADED"
    else:
        health = "HEALTHY"

    return {
        "status": health,
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "runner_status": status,
        "runner_mode": result.get("mode"),
        "execution_submitted": submitted,
        "consecutive_errors": max(
            0,
            int(consecutive_errors),
        ),
        "maximum_consecutive_errors": max(
            1,
            int(maximum_consecutive_errors),
        ),
        "issues": issues,
        "diagnostics_only": True,
    }
