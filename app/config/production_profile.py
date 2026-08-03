"""TitanAI production profile v33."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any

SUPPORTED_ENVIRONMENTS = {"DEVELOPMENT", "TESTNET", "MAINNET"}


def _boolean(source: dict, name: str, default: bool = False) -> bool:
    value = str(source.get(name, "true" if default else "false")).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _number(source: dict, name: str, default: float) -> float:
    try:
        return float(source.get(name, default))
    except (TypeError, ValueError):
        return default


def _integer(source: dict, name: str, default: int) -> int:
    try:
        return int(source.get(name, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ProductionProfile:
    environment: str
    execution_enabled: bool
    mainnet_confirmed: bool
    strict_startup_validation: bool
    maximum_risk_percent: float
    maximum_leverage: float
    maximum_position_percent: float
    maximum_daily_loss_percent: float
    maximum_concurrent_positions: int
    telegram_enabled: bool
    runner_exchange_mode: str = "BINANCE_FUTURES_TESTNET"
    version: str = "v33"

    @property
    def is_mainnet(self) -> bool:
        return self.environment == "MAINNET"

    @property
    def is_testnet(self) -> bool:
        return self.environment == "TESTNET"

    def to_dict(self) -> dict:
        return asdict(self)


def load_production_profile(environ: dict[str, Any] | None = None) -> ProductionProfile:
    import os
    source = dict(os.environ) if environ is None else dict(environ)
    environment = str(source.get("TITANAI_ENVIRONMENT", "TESTNET")).strip().upper()
    if environment not in SUPPORTED_ENVIRONMENTS:
        environment = "INVALID"

    return ProductionProfile(
        environment=environment,
        execution_enabled=_boolean(source, "TITANAI_EXECUTION_ENABLED"),
        mainnet_confirmed=_boolean(source, "TITANAI_MAINNET_CONFIRMED"),
        strict_startup_validation=_boolean(
            source,
            "TITANAI_STRICT_STARTUP_VALIDATION",
        ),
        maximum_risk_percent=_number(
            source,
            "TITANAI_MAXIMUM_RISK_PERCENT",
            2.0,
        ),
        maximum_leverage=_number(
            source,
            "TITANAI_MAXIMUM_LEVERAGE",
            5.0,
        ),
        maximum_position_percent=_number(
            source,
            "TITANAI_MAXIMUM_POSITION_PERCENT",
            25.0,
        ),
        maximum_daily_loss_percent=_number(
            source,
            "TITANAI_MAXIMUM_DAILY_LOSS_PERCENT",
            3.0,
        ),
        maximum_concurrent_positions=_integer(
            source,
            "TITANAI_MAXIMUM_CONCURRENT_POSITIONS",
            1,
        ),
        telegram_enabled=_boolean(source, "TITANAI_TELEGRAM_ENABLED"),
    )
