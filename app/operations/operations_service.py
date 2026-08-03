"""TitanAI Operations Service v35.1."""

from __future__ import annotations

from app.operations.health_monitor import (
    check_operations_health,
)
from app.operations.service_supervisor import (
    supervise_service_health,
)


def build_operations_snapshot() -> dict:
    """Return one non-blocking operations snapshot."""
    try:
        health = check_operations_health()
        supervision = (
            supervise_service_health(
                health
            )
        )

        return {
            "status": "success",
            "version": "v35.1",
            "health": health,
            "supervision": supervision,
            "non_blocking": True,
            "read_only": True,
        }

    except Exception as error:
        return {
            "status": "error",
            "version": "v35.1",
            "health": {
                "status": "CRITICAL",
                "healthy": False,
                "errors": [str(error)],
            },
            "supervision": {
                "status": "error",
                "action": "PAUSE",
                "reason": str(error),
            },
            "errors": [str(error)],
            "non_blocking": True,
            "read_only": True,
        }
