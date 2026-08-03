"""Optional Telegram Notifier v32.

Disabled by default. Configuration:

- TITANAI_TELEGRAM_ENABLED=true
- TITANAI_TELEGRAM_BOT_TOKEN=...
- TITANAI_TELEGRAM_CHAT_ID=...
"""

from __future__ import annotations

import json
import os
from typing import Callable
from urllib import parse, request

from app.notifications.alert_formatter import (
    format_alert,
)


def _enabled() -> bool:
    return str(
        os.getenv(
            "TITANAI_TELEGRAM_ENABLED",
            "false",
        )
    ).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def send_telegram_notification(
    notification: dict,
    *,
    transport: Callable | None = None,
    timeout_seconds: float = 5.0,
) -> dict:
    if not _enabled():
        return {
            "status": "disabled",
            "sent": False,
            "reason": (
                "Telegram notifications are "
                "disabled"
            ),
        }

    token = str(
        os.getenv(
            "TITANAI_TELEGRAM_BOT_TOKEN",
            "",
        )
    ).strip()
    chat_id = str(
        os.getenv(
            "TITANAI_TELEGRAM_CHAT_ID",
            "",
        )
    ).strip()

    if not token or not chat_id:
        return {
            "status": "misconfigured",
            "sent": False,
            "reason": (
                "Telegram token or chat ID "
                "is missing"
            ),
        }

    payload = parse.urlencode(
        {
            "chat_id": chat_id,
            "text": format_alert(
                notification
            ),
            "disable_web_page_preview": (
                "true"
            ),
        }
    ).encode("utf-8")

    url = (
        "https://api.telegram.org/"
        f"bot{token}/sendMessage"
    )

    try:
        if transport is not None:
            response_payload = transport(
                url,
                payload,
                timeout_seconds,
            )
        else:
            http_request = request.Request(
                url,
                data=payload,
                method="POST",
                headers={
                    "Content-Type": (
                        "application/"
                        "x-www-form-urlencoded"
                    ),
                },
            )

            with request.urlopen(
                http_request,
                timeout=timeout_seconds,
            ) as response:
                response_payload = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

        success = bool(
            (
                response_payload
                if isinstance(
                    response_payload,
                    dict,
                )
                else {}
            ).get("ok")
        )

        return {
            "status": (
                "sent"
                if success
                else "failed"
            ),
            "sent": success,
            "response": response_payload,
        }

    except Exception as error:
        return {
            "status": "failed",
            "sent": False,
            "reason": str(error),
        }
