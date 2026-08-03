"""TitanAI Order Recovery Engine v28.

The engine rebuilds local open-order state from a verified Binance Testnet
snapshot and reports unresolved terminal orders. It never submits or cancels
orders.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.trader.order_consistency_audit import (
    build_order_consistency_audit,
    normalise_exchange_order,
)
from app.trader.order_recovery_store import (
    list_order_states,
    mark_disappeared_orders,
    upsert_open_order,
)
from app.trader.persistent_trade_state import (
    record_event,
)


def recover_open_orders(
    *,
    exchange_orders: list[dict] | None,
    open_positions: list[dict] | None,
) -> dict:
    if not isinstance(
        exchange_orders,
        list,
    ):
        return {
            "status": "blocked",
            "version": "v28",
            "reason": (
                "Exchange open-order snapshot "
                "must be a verified list"
            ),
            "mutation_performed": False,
            "execution_submitted": False,
            "orders_cancelled": 0,
            "orders_submitted": 0,
            "errors": [
                "Invalid exchange-order snapshot"
            ],
        }

    local_before = list_order_states(
        status="OPEN"
    )
    audit_before = (
        build_order_consistency_audit(
            exchange_orders=exchange_orders,
            local_open_orders=local_before,
            open_positions=(
                open_positions or []
            ),
        )
    )

    normalised_orders = []
    errors: list[str] = []

    for order in exchange_orders:
        normalised = (
            normalise_exchange_order(
                order
            )
        )

        if normalised is None:
            errors.append(
                "One exchange order could "
                "not be normalised"
            )
            continue

        normalised_orders.append(
            normalised
        )

        try:
            upsert_open_order(
                normalised
            )
        except Exception as error:
            errors.append(
                "Local order upsert failed "
                f"for {normalised['order_key']}: "
                f"{error}"
            )

    active_keys = {
        order["order_key"]
        for order in normalised_orders
    }

    try:
        unresolved_terminal_orders = (
            mark_disappeared_orders(
                active_keys
            )
        )
    except Exception as error:
        unresolved_terminal_orders = []
        errors.append(
            "Missing-order classification "
            f"failed: {error}"
        )

    local_after = list_order_states(
        status="OPEN"
    )
    audit_after = (
        build_order_consistency_audit(
            exchange_orders=exchange_orders,
            local_open_orders=local_after,
            open_positions=(
                open_positions or []
            ),
        )
    )

    try:
        record_event(
            "ORDER_RECOVERY_SYNC",
            {
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(
                    timespec="milliseconds"
                ),
                "audit_before": audit_before,
                "audit_after": audit_after,
                "unresolved_terminal_orders": (
                    unresolved_terminal_orders
                ),
            },
        )
    except Exception as error:
        errors.append(
            "Order recovery event could "
            f"not be recorded: {error}"
        )

    unresolved_count = len(
        unresolved_terminal_orders
    )

    return {
        "status": (
            "success"
            if (
                not errors
                and audit_after.get(
                    "status"
                )
                == "consistent"
                and unresolved_count == 0
            )
            else "review_required"
            if (
                audit_after.get(
                    "status"
                )
                == "consistent"
            )
            else "drift_detected"
        ),
        "version": "v28",
        "source_of_truth": (
            "BINANCE_TESTNET"
        ),
        "mutation_performed": True,
        "execution_submitted": False,
        "orders_cancelled": 0,
        "orders_submitted": 0,
        "exchange_open_order_count": len(
            normalised_orders
        ),
        "audit_before": audit_before,
        "audit_after": audit_after,
        "unresolved_terminal_orders": (
            unresolved_terminal_orders
        ),
        "requires_terminal_status_query": (
            unresolved_count > 0
        ),
        "errors": errors,
    }
