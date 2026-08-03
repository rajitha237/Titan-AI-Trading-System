"""TitanAI Production Readiness Report v35.3."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.config.startup_checks import (
    evaluate_startup_readiness,
)
from app.operations.operations_service import (
    build_operations_snapshot,
)
from app.operations.operations_backup_service import (
    build_backup_operations_snapshot,
)
from app.performance.performance_service import (
    build_and_store_performance,
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat(timespec="milliseconds")


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def build_production_readiness_report(
    *,
    execute_trade_requested: bool = False,
) -> dict:
    """Build one diagnostics-only production readiness report."""
    startup = evaluate_startup_readiness(
        execute_trade_requested=(
            execute_trade_requested
        )
    )
    operations = (
        build_operations_snapshot()
    )
    backup = (
        build_backup_operations_snapshot()
    )
    performance = (
        build_and_store_performance(
            completed_trades=[],
            starting_equity=0.0,
        )
    )

    health = _safe_dict(
        operations.get("health")
    )
    supervision = _safe_dict(
        operations.get("supervision")
    )

    checks = {
        "startup_configuration": (
            startup.get(
                "startup_allowed"
            )
            is True
        ),
        "operations_health": (
            health.get("status")
            in {
                "HEALTHY",
                "WARNING",
            }
        ),
        "service_supervision": (
            supervision.get("action")
            in {
                "CONTINUE",
                "PAUSE",
            }
        ),
        "backup_service": (
            backup.get("status")
            == "success"
        ),
        "performance_reporting": (
            performance.get("status")
            == "success"
        ),
        "mainnet_disabled": (
            startup.get(
                "profile",
                {},
            ).get("environment")
            != "MAINNET"
        ),
    }

    failed_checks = [
        name
        for name, passed in checks.items()
        if not passed
    ]

    status = (
        "READY"
        if not failed_checks
        else "NOT_READY"
    )

    return {
        "status": status,
        "version": "v35.3",
        "generated_at": _utc_now(),
        "ready": not failed_checks,
        "execution_requested": (
            execute_trade_requested
        ),
        "checks": checks,
        "failed_checks": failed_checks,
        "startup": startup,
        "operations": operations,
        "backup": backup,
        "performance": performance,
        "mainnet_supported": False,
        "testnet_only": True,
        "read_only": True,
    }
