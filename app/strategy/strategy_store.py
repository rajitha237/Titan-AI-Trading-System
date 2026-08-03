"""
TitanAI Strategy Settings Store
"""

import json
from datetime import datetime
from pathlib import Path

STRATEGY_FILE = Path("data/strategy_settings.json")


def save_strategy_settings(settings: dict) -> dict:
    STRATEGY_FILE.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "updated_at": datetime.utcnow().isoformat(),
        "settings": settings,
    }

    with open(STRATEGY_FILE, "w") as file:
        json.dump(payload, file, indent=2)

    return {
        "status": "saved",
        "file": str(STRATEGY_FILE),
        "updated_at": payload["updated_at"],
    }


def load_strategy_settings() -> dict:
    if not STRATEGY_FILE.exists():
        return {
            "updated_at": None,
            "settings": {},
        }

    with open(STRATEGY_FILE, "r") as file:
        return json.load(file)


def get_strategy(symbol: str) -> dict | None:
    data = load_strategy_settings()
    settings = data.get("settings", {})
    return settings.get(symbol)