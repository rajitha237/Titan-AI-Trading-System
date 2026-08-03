"""Secure Telegram notification client for TitanAI.

Secrets are loaded from environment variables:
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID

Never hard-code or commit the bot token.
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx


def _load_dotenv(path: str | Path = ".env") -> None:
    """Load simple KEY=VALUE entries without overriding existing variables."""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    enabled: bool = True
    timeout_seconds: float = 15.0

    @classmethod
    def from_env(cls) -> "TelegramConfig":
        _load_dotenv()

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        enabled_value = os.getenv("TITANAI_TELEGRAM_ENABLED", "true").strip().lower()
        enabled = enabled_value in {"1", "true", "yes", "on"}

        try:
            timeout = float(os.getenv("TITANAI_TELEGRAM_TIMEOUT_SECONDS", "15"))
        except ValueError:
            timeout = 15.0

        return cls(
            bot_token=token,
            chat_id=chat_id,
            enabled=enabled,
            timeout_seconds=max(5.0, timeout),
        )

    @property
    def configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)


class TelegramService:
    def __init__(self, config: TelegramConfig | None = None) -> None:
        self.config = config or TelegramConfig.from_env()

    async def send_message(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        disable_notification: bool = False,
    ) -> dict[str, Any]:
        if not self.config.enabled:
            return {"status": "disabled", "sent": False}

        if not self.config.configured:
            return {
                "status": "not_configured",
                "sent": False,
                "reason": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing",
            }

        clean_text = str(text).strip()
        if not clean_text:
            return {
                "status": "skipped",
                "sent": False,
                "reason": "Message text was empty",
            }

        url = f"https://api.telegram.org/bot{self.config.bot_token}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": self.config.chat_id,
            "text": clean_text[:4096],
            "disable_notification": disable_notification,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode

        try:
            async with httpx.AsyncClient(
                timeout=self.config.timeout_seconds
            ) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()

            if not data.get("ok"):
                return {
                    "status": "error",
                    "sent": False,
                    "reason": data.get("description", "Telegram rejected the message"),
                }

            return {
                "status": "success",
                "sent": True,
                "message_id": (data.get("result") or {}).get("message_id"),
            }

        except httpx.HTTPStatusError as error:
            detail = ""
            try:
                detail = error.response.json().get("description", "")
            except Exception:
                detail = error.response.text[:300]

            return {
                "status": "error",
                "sent": False,
                "reason": f"Telegram HTTP {error.response.status_code}: {detail}",
            }

        except Exception as error:
            return {
                "status": "error",
                "sent": False,
                "reason": str(error),
            }


async def send_telegram_message(text: str) -> dict[str, Any]:
    return await TelegramService().send_message(text)