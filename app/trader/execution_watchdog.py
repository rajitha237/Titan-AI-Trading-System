"""TitanAI Execution Watchdog v29.

Combines exchange health, state-recovery results, and a circuit breaker into a
single pre-scan safety decision.
"""

from __future__ import annotations

from typing import Any, Callable

from app.monitoring.exchange_health_monitor import (
    check_exchange_health,
)
from app.monitoring.circuit_breaker import (
    CircuitBreaker,
)
from app.monitoring.persistent_circuit_breaker import (
    PersistentCircuitBreaker,
)


GLOBAL_EXECUTION_BREAKER = PersistentCircuitBreaker(
    state_key="execution_watchdog_breaker",
    failure_threshold=3,
    recovery_timeout_seconds=60.0,
)


def _status_is_acceptable(
    payload: Any,
    acceptable: set[str],
) -> bool:
    if not isinstance(payload, dict):
        return False

    return str(
        payload.get("status", "")
    ).lower() in acceptable


def evaluate_execution_watchdog(
    *,
    position_sync: dict | None,
    order_recovery: dict | None,
    health_function: Callable[[], dict] = (
        check_exchange_health
    ),
    circuit_breaker: CircuitBreaker = (
        GLOBAL_EXECUTION_BREAKER
    ),
) -> dict:
    """Return a diagnostics-first execution permission decision."""
    block_reasons: list[str] = []

    if not circuit_breaker.allow_request():
        block_reasons.append(
            "Execution circuit breaker is open"
        )

    try:
        exchange_health = health_function()
    except Exception as error:
        exchange_health = {
            "status": "degraded",
            "healthy": False,
            "errors": [str(error)],
        }

    if (
        not isinstance(exchange_health, dict)
        or exchange_health.get("healthy")
        is not True
    ):
        block_reasons.append(
            "Exchange health check did not pass"
        )

    if not _status_is_acceptable(
        position_sync,
        {
            "success",
            "partial",
        },
    ):
        block_reasons.append(
            "Live position synchronization "
            "is not healthy"
        )

    if not _status_is_acceptable(
        order_recovery,
        {
            "success",
            "review_required",
        },
    ):
        block_reasons.append(
            "Order recovery is not healthy"
        )

    if isinstance(
        order_recovery,
        dict,
    ):
        audit_after = (
            order_recovery.get(
                "audit_after",
                {},
            )
            or {}
        )

        if (
            audit_after.get("status")
            == "drift_detected"
        ):
            block_reasons.append(
                "Order-state drift remains unresolved"
            )

    allowed = not block_reasons

    if allowed:
        circuit_breaker.record_success()
    else:
        circuit_breaker.record_failure(
            "; ".join(block_reasons)
        )

    return {
        "status": (
            "ready"
            if allowed
            else "blocked"
        ),
        "version": "v29",
        "allowed": allowed,
        "exchange_health": exchange_health,
        "position_sync_status": (
            (position_sync or {}).get(
                "status"
            )
            if isinstance(
                position_sync,
                dict,
            )
            else None
        ),
        "order_recovery_status": (
            (order_recovery or {}).get(
                "status"
            )
            if isinstance(
                order_recovery,
                dict,
            )
            else None
        ),
        "block_reasons": list(
            dict.fromkeys(
                block_reasons
            )
        ),
        "circuit_breaker": (
            circuit_breaker.snapshot()
        ),
        "execution_submitted": False,
        "diagnostics_only": True,
    }
