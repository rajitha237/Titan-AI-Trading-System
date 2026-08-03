"""TitanAI Notification Models v32."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any


SEVERITIES = {
    "INFO",
    "WARNING",
    "CRITICAL",
}

EVENT_TYPES = {
    "TRADE_SUBMITTED",
    "POSITION_CLOSED",
    "WATCHDOG_BLOCKED",
    "EXCHANGE_UNHEALTHY",
    "ORDER_RECOVERY_REVIEW",
    "POSITION_SYNC_DRIFT",
    "RISK_BLOCKED",
    "SYSTEM_ERROR",
    "LEARNING_MILESTONE",
}


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def build_notification(
    *,
    event_type: str,
    severity: str,
    title: str,
    message: str,
    cycle_id: str | None = None,
    symbol: str | None = None,
    data: dict | None = None,
    event_key: str | None = None,
) -> dict:
    event_type = str(
        event_type or ""
    ).strip().upper()
    severity = str(
        severity or ""
    ).strip().upper()

    if event_type not in EVENT_TYPES:
        raise ValueError(
            f"Unsupported event_type: {event_type}"
        )

    if severity not in SEVERITIES:
        raise ValueError(
            f"Unsupported severity: {severity}"
        )

    payload = {
        "event_type": event_type,
        "severity": severity,
        "title": str(title).strip(),
        "message": str(message).strip(),
        "cycle_id": (
            str(cycle_id)
            if cycle_id
            else None
        ),
        "symbol": (
            str(symbol).upper()
            if symbol
            else None
        ),
        "data": _safe_dict(data),
        "created_at": _utc_now(),
        "version": "v32",
    }

    if not payload["title"]:
        raise ValueError(
            "Notification title is required"
        )

    if not payload["message"]:
        raise ValueError(
            "Notification message is required"
        )

    if event_key:
        payload["event_key"] = str(
            event_key
        )
    else:
        identity = {
            "event_type": event_type,
            "cycle_id": payload["cycle_id"],
            "symbol": payload["symbol"],
            "title": payload["title"],
            "data": payload["data"],
        }
        digest = hashlib.sha256(
            json.dumps(
                identity,
                sort_keys=True,
                default=str,
            ).encode("utf-8")
        ).hexdigest()[:24]
        payload["event_key"] = (
            f"{event_type}:{digest}"
        )

    return payload
