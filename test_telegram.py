"""Send a TitanAI Telegram connection test."""

from __future__ import annotations

import asyncio
import sys

from app.notifications.telegram_service import TelegramService


async def main() -> int:
    service = TelegramService()
    result = await service.send_message(
        "✅ TitanAI connected successfully\n\nTelegram notifications are ready."
    )

    if result.get("sent") is True:
        print("Telegram test message sent successfully.")
        return 0

    print("Telegram test failed:")
    print(result.get("reason", result.get("status", "Unknown error")))
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))