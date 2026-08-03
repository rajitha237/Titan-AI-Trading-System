"""Persist autonomous-service heartbeat state."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HEARTBEAT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "service"
    / "autonomous_heartbeat.json"
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


def write_heartbeat(
    *,
    status: str,
    cycle_number: int,
    execute_trade: bool,
    interval_seconds: float,
    last_result: dict | None = None,
    error: str | None = None,
) -> dict:
    """Atomically write the latest service heartbeat."""
    HEARTBEAT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = (
        last_result
        if isinstance(last_result, dict)
        else {}
    )
    execution = result.get("execution")
    execution = (
        execution
        if isinstance(execution, dict)
        else {}
    )

    payload = {
        "status": str(status).upper(),
        "timestamp": _utc_now(),
        "process_id": os.getpid(),
        "cycle_number": max(
            0,
            int(cycle_number),
        ),
        "execute_trade": bool(execute_trade),
        "interval_seconds": float(
            interval_seconds
        ),
        "last_cycle": {
            "status": result.get("status"),
            "mode": result.get("mode"),
            "symbol": result.get("symbol"),
            "cycle_id": result.get("cycle_id"),
            "learning_status": result.get(
                "learning_status"
            ),
            "execution_submitted": bool(
                execution.get(
                    "submitted",
                    False,
                )
            ),
        },
        "error": error,
    }

    temporary_path = HEARTBEAT_PATH.with_suffix(
        ".tmp"
    )
    temporary_path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    temporary_path.replace(
        HEARTBEAT_PATH
    )

    return payload


def read_heartbeat() -> dict:
    if not HEARTBEAT_PATH.exists():
        return {
            "status": "NOT_STARTED",
            "path": str(HEARTBEAT_PATH),
        }

    try:
        return json.loads(
            HEARTBEAT_PATH.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ) as error:
        return {
            "status": "ERROR",
            "path": str(HEARTBEAT_PATH),
            "error": str(error),
        }
