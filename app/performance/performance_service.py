"""TitanAI Non-Blocking Performance Service v34."""

from __future__ import annotations

from datetime import datetime, timezone

from app.performance.performance_dashboard import (
    build_performance_dashboard,
)
from app.performance.performance_history import (
    save_performance_snapshot,
)


def _utc_date() -> str:
    return datetime.now(
        timezone.utc
    ).date().isoformat()


def build_and_store_performance(
    *,
    completed_trades: list[dict] | None,
    starting_equity: float = 0.0,
) -> dict:
    try:
        dashboard = (
            build_performance_dashboard(
                trades=completed_trades,
                starting_equity=(
                    starting_equity
                ),
            )
        )

        snapshot = (
            save_performance_snapshot(
                snapshot_key=(
                    f"daily:{_utc_date()}"
                ),
                payload=dashboard,
            )
        )

        return {
            "status": "success",
            "version": "v34",
            "dashboard": dashboard,
            "snapshot": snapshot,
            "non_blocking": True,
        }

    except Exception as error:
        return {
            "status": "error",
            "version": "v34",
            "dashboard": {
                "status": "error",
                "version": "v34",
                "error": str(error),
            },
            "snapshot": None,
            "errors": [str(error)],
            "non_blocking": True,
        }
