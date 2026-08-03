"""TitanAI Startup Launcher v35.3."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from app.config.startup_checks import (
    evaluate_startup_readiness,
)
from app.operations.production_report import (
    build_production_readiness_report,
)
from app.trader.auto_testnet_runner import (
    run_auto_testnet_cycle,
)


def _env_bool(
    name: str,
    default: bool = False,
) -> bool:
    value = str(
        os.getenv(
            name,
            "true" if default else "false",
        )
    ).strip().lower()

    return value in {
        "1",
        "true",
        "yes",
        "on",
    }


async def launch_once(
    *,
    execute_trade: bool | None = None,
    scan_limit: int = 5,
) -> dict:
    """Run one validated TitanAI cycle."""
    if execute_trade is None:
        execute_trade = _env_bool(
            "TITANAI_EXECUTION_ENABLED",
            False,
        )

    startup = evaluate_startup_readiness(
        execute_trade_requested=(
            execute_trade
        )
    )

    if (
        startup.get(
            "startup_allowed"
        )
        is not True
    ):
        return {
            "status": "blocked",
            "version": "v35.3",
            "mode": (
                "STARTUP_CONFIGURATION_LOCK"
            ),
            "startup": startup,
            "execution": {
                "submitted": False,
                "status": "blocked",
            },
        }

    readiness = (
        build_production_readiness_report(
            execute_trade_requested=(
                execute_trade
            )
        )
    )

    if readiness.get("ready") is not True:
        return {
            "status": "blocked",
            "version": "v35.3",
            "mode": (
                "PRODUCTION_READINESS_LOCK"
            ),
            "readiness": readiness,
            "execution": {
                "submitted": False,
                "status": "blocked",
            },
        }

    result = await run_auto_testnet_cycle(
        execute_trade=execute_trade,
        scan_limit=scan_limit,
    )

    result["launcher"] = {
        "status": "success",
        "version": "v35.3",
        "validated_before_run": True,
        "testnet_only": True,
    }

    return result


def launch_once_sync(
    *,
    execute_trade: bool | None = None,
    scan_limit: int = 5,
) -> dict:
    return asyncio.run(
        launch_once(
            execute_trade=execute_trade,
            scan_limit=scan_limit,
        )
    )
