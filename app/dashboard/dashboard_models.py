"""TitanAI dashboard helpers v31."""
from __future__ import annotations
from typing import Any


def safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return default
        return number
    except (TypeError, ValueError):
        return default


def normalise_status(value: Any, default: str = "unknown") -> str:
    text = str(value if value is not None else default).strip().lower()
    return text or default


def section(status: Any, summary: str, data: dict | None = None, warnings: list | None = None) -> dict:
    return {
        "status": normalise_status(status),
        "summary": str(summary),
        "data": safe_dict(data),
        "warnings": [str(item) for item in safe_list(warnings)],
    }
