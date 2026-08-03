"""TitanAI Service State Manager v30."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.service.service_state_store import (
    get_latest_heartbeat,
    record_heartbeat,
    set_state,
)


SERVICE_NAME = "titanai_autonomous_runner"


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


def begin_service_cycle(
    *,
    mode: str,
) -> dict:
    cycle_id = str(uuid.uuid4())
    started_at = _utc_now()

    set_state(
        "service_runtime",
        {
            "service_name": SERVICE_NAME,
            "status": "RUNNING",
            "mode": mode,
            "cycle_id": cycle_id,
            "started_at": started_at,
        },
    )

    record_heartbeat(
        service_name=SERVICE_NAME,
        status="RUNNING",
        mode=mode,
        cycle_id=cycle_id,
        payload={
            "started_at": started_at,
        },
    )

    return {
        "service_name": SERVICE_NAME,
        "cycle_id": cycle_id,
        "started_at": started_at,
        "mode": mode,
        "status": "RUNNING",
    }


def complete_service_cycle(
    *,
    cycle_context: dict,
    result: dict,
) -> dict:
    cycle_id = str(
        cycle_context.get(
            "cycle_id",
            "",
        )
    )
    mode = str(
        result.get(
            "mode",
            cycle_context.get(
                "mode",
                "UNKNOWN",
            ),
        )
    )
    status = str(
        result.get(
            "status",
            "unknown",
        )
    )
    completed_at = _utc_now()

    state = {
        "service_name": SERVICE_NAME,
        "status": status,
        "mode": mode,
        "cycle_id": cycle_id,
        "started_at": (
            cycle_context.get(
                "started_at"
            )
        ),
        "completed_at": completed_at,
        "submitted": bool(
            (
                result.get("execution")
                or {}
            ).get(
                "submitted",
                False,
            )
        ),
    }

    set_state(
        "service_runtime",
        state,
    )

    heartbeat_id = record_heartbeat(
        service_name=SERVICE_NAME,
        status=status,
        mode=mode,
        cycle_id=cycle_id,
        payload=state,
    )

    return {
        **state,
        "heartbeat_id": heartbeat_id,
    }


def build_service_state_snapshot() -> dict:
    latest = get_latest_heartbeat(
        SERVICE_NAME
    )

    return {
        "status": "ready",
        "version": "v30",
        "service_name": SERVICE_NAME,
        "latest_heartbeat": latest,
        "persistent": True,
    }
