"""TitanAI Alert Formatter v32."""

from __future__ import annotations

from typing import Any


SEVERITY_ICON = {
    "INFO": "ℹ️",
    "WARNING": "⚠️",
    "CRITICAL": "🚨",
}


def format_alert(
    notification: dict | None,
) -> str:
    notification = (
        notification
        if isinstance(
            notification,
            dict,
        )
        else {}
    )

    severity = str(
        notification.get(
            "severity",
            "INFO",
        )
    ).upper()
    icon = SEVERITY_ICON.get(
        severity,
        "ℹ️",
    )
    title = str(
        notification.get(
            "title",
            "TitanAI Alert",
        )
    )
    message = str(
        notification.get(
            "message",
            "",
        )
    )
    symbol = notification.get("symbol")
    cycle_id = notification.get(
        "cycle_id"
    )

    lines = [
        f"{icon} TitanAI — {title}",
        message,
    ]

    if symbol:
        lines.append(
            f"Symbol: {symbol}"
        )

    if cycle_id:
        lines.append(
            f"Cycle: {cycle_id}"
        )

    return "\n".join(lines)


def compact_notification_summary(
    result: dict | None,
) -> str:
    result = (
        result
        if isinstance(result, dict)
        else {}
    )

    return (
        "notifications="
        f"{result.get('event_count', 0)} "
        "stored="
        f"{result.get('stored_count', 0)} "
        "telegram_sent="
        f"{result.get('telegram_sent_count', 0)}"
    )
