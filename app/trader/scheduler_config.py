"""TitanAI scheduler configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float, minimum: float | None = None) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value) if minimum is not None else value


def _env_int(name: str, default: int, minimum: int | None = None) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    return max(minimum, value) if minimum is not None else value


@dataclass(frozen=True)
class SchedulerConfig:
    interval_seconds: float = 30.0
    error_retry_seconds: float = 15.0
    execute_trades: bool = False
    balance: float = 30.0
    risk_percent: float = 1.0
    leverage: float = 5.0
    scan_limit: int = 20
    current_daily_pnl: float = 0.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "SchedulerConfig":
        return cls(
            interval_seconds=_env_float("TITANAI_INTERVAL_SECONDS", 30.0, 5.0),
            error_retry_seconds=_env_float("TITANAI_ERROR_RETRY_SECONDS", 15.0, 5.0),
            execute_trades=_env_bool("TITANAI_EXECUTE_TRADES", False),
            balance=_env_float("TITANAI_BALANCE", 30.0, 0.0),
            risk_percent=_env_float("TITANAI_RISK_PERCENT", 1.0, 0.0),
            leverage=_env_float("TITANAI_LEVERAGE", 5.0, 1.0),
            scan_limit=_env_int("TITANAI_SCAN_LIMIT", 20, 1),
            current_daily_pnl=_env_float("TITANAI_CURRENT_DAILY_PNL", 0.0),
            log_level=os.getenv("TITANAI_LOG_LEVEL", "INFO").upper(),
        )