"""Redacted secret discovery v33."""
from __future__ import annotations
import os
from typing import Any

ALIASES = {
    "binance_api_key": (
        "BINANCE_TESTNET_API_KEY",
        "BINANCE_API_KEY",
        "TITANAI_BINANCE_API_KEY",
    ),
    "binance_api_secret": (
        "BINANCE_TESTNET_API_SECRET",
        "BINANCE_API_SECRET",
        "TITANAI_BINANCE_API_SECRET",
    ),
    "telegram_bot_token": ("TITANAI_TELEGRAM_BOT_TOKEN",),
    "telegram_chat_id": ("TITANAI_TELEGRAM_CHAT_ID",),
}
PLACEHOLDERS = {
    "", "changeme", "change_me", "your_api_key", "your_api_secret",
    "your_bot_token", "your_chat_id", "replace_me", "example", "none", "null",
}


def _placeholder(value: str | None) -> bool:
    if value is None:
        return False
    text = value.strip().lower().replace("-", "_").replace(" ", "_")
    return text in PLACEHOLDERS or text.startswith(("your_", "replace_"))


def load_secret_bundle(environ: dict[str, Any] | None = None) -> dict:
    source = os.environ if environ is None else environ
    values = {}
    diagnostics = {}

    for logical_name, aliases in ALIASES.items():
        value = None
        source_name = None
        for name in aliases:
            candidate = str(source.get(name, "")).strip()
            if candidate:
                value = candidate
                source_name = name
                break
        values[logical_name] = value
        diagnostics[logical_name] = {
            "present": bool(value),
            "placeholder": _placeholder(value),
            "source_variable": source_name,
        }

    return {
        "values": values,
        "diagnostics": diagnostics,
        "version": "v33",
    }


def redact_secret(value: str | None) -> str:
    return "[REDACTED]" if value else "[MISSING]"
