"""TitanAI Live Position Synchronizer v27.

Binance is treated as the source of truth. This module performs diagnostics,
closed-position lifecycle reconciliation, and restart-safe local-state recovery.
It never submits, cancels, or closes exchange orders.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from app.trader.persistent_trade_state import (
    list_position_states,
    record_event,
    sync_cycle_state,
)
from app.trader.position_lifecycle import (
    reconcile_closed_positions,
)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)
        if (
            number != number
            or number
            in {
                float("inf"),
                float("-inf"),
            }
        ):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _normalise_exchange_position(
    position: Any,
) -> dict | None:
    if not isinstance(position, dict):
        return None

    symbol = str(
        position.get("symbol", "")
    ).strip().upper()

    amount = _safe_float(
        position.get(
            "positionAmt",
            position.get(
                "position_amount",
                position.get("quantity", 0.0),
            ),
        ),
        0.0,
    )

    entry_price = _safe_float(
        position.get(
            "entryPrice",
            position.get("entry_price", 0.0),
        ),
        0.0,
    )

    mark_price = _safe_float(
        position.get(
            "markPrice",
            position.get("mark_price", 0.0),
        ),
        0.0,
    )

    if (
        not symbol
        or amount == 0.0
        or entry_price <= 0.0
    ):
        return None

    side = "BUY" if amount > 0 else "SELL"

    return {
        "symbol": symbol,
        "side": side,
        "quantity": abs(amount),
        "signed_quantity": amount,
        "entry_price": entry_price,
        "mark_price": mark_price,
        "raw": position,
    }


def _exchange_key(
    position: dict,
) -> tuple[str, str]:
    return (
        str(position.get("symbol", "")).upper(),
        str(position.get("side", "")).upper(),
    )


def _local_key(
    state: dict,
) -> tuple[str, str]:
    return (
        str(state.get("symbol", "")).upper(),
        str(state.get("side", "")).upper(),
    )


def build_position_consistency_audit(
    *,
    exchange_positions: list[dict] | None,
    local_open_states: list[dict] | None,
) -> dict:
    """Compare Binance truth with local OPEN states without mutating either."""
    normalised_exchange = []

    for position in exchange_positions or []:
        normalised = _normalise_exchange_position(
            position
        )
        if normalised is not None:
            normalised_exchange.append(
                normalised
            )

    local_states = [
        state
        for state in (local_open_states or [])
        if isinstance(state, dict)
        and str(
            state.get("status", "OPEN")
        ).upper()
        == "OPEN"
    ]

    exchange_by_key = {
        _exchange_key(position): position
        for position in normalised_exchange
    }
    local_by_key = {
        _local_key(state): state
        for state in local_states
    }

    exchange_keys = set(exchange_by_key)
    local_keys = set(local_by_key)

    missing_local = sorted(
        exchange_keys - local_keys
    )
    missing_exchange = sorted(
        local_keys - exchange_keys
    )

    quantity_mismatches = []
    entry_price_mismatches = []

    for key in sorted(
        exchange_keys & local_keys
    ):
        exchange = exchange_by_key[key]
        local = local_by_key[key]

        exchange_quantity = _safe_float(
            exchange.get("quantity")
        )
        local_quantity = _safe_float(
            local.get("current_quantity")
        )

        quantity_tolerance = max(
            exchange_quantity * 0.001,
            1e-12,
        )

        if (
            abs(
                exchange_quantity
                - local_quantity
            )
            > quantity_tolerance
        ):
            quantity_mismatches.append(
                {
                    "symbol": key[0],
                    "side": key[1],
                    "exchange_quantity": (
                        exchange_quantity
                    ),
                    "local_quantity": (
                        local_quantity
                    ),
                }
            )

        exchange_entry = _safe_float(
            exchange.get("entry_price")
        )
        local_entry = _safe_float(
            local.get("entry_price")
        )

        entry_tolerance = max(
            exchange_entry * 0.0005,
            1e-12,
        )

        if (
            abs(exchange_entry - local_entry)
            > entry_tolerance
        ):
            entry_price_mismatches.append(
                {
                    "symbol": key[0],
                    "side": key[1],
                    "exchange_entry_price": (
                        exchange_entry
                    ),
                    "local_entry_price": (
                        local_entry
                    ),
                }
            )

    duplicate_exchange_keys = []
    seen_exchange = set()

    for position in normalised_exchange:
        key = _exchange_key(position)
        if key in seen_exchange:
            duplicate_exchange_keys.append(
                {
                    "symbol": key[0],
                    "side": key[1],
                }
            )
        seen_exchange.add(key)

    issues = (
        len(missing_local)
        + len(missing_exchange)
        + len(quantity_mismatches)
        + len(entry_price_mismatches)
        + len(duplicate_exchange_keys)
    )

    return {
        "status": (
            "consistent"
            if issues == 0
            else "drift_detected"
        ),
        "version": "v27",
        "diagnostics_only": True,
        "exchange_position_count": len(
            normalised_exchange
        ),
        "local_open_state_count": len(
            local_states
        ),
        "missing_local_states": [
            {
                "symbol": symbol,
                "side": side,
            }
            for symbol, side in missing_local
        ],
        "missing_exchange_positions": [
            {
                "symbol": symbol,
                "side": side,
            }
            for symbol, side
            in missing_exchange
        ],
        "quantity_mismatches": (
            quantity_mismatches
        ),
        "entry_price_mismatches": (
            entry_price_mismatches
        ),
        "duplicate_exchange_positions": (
            duplicate_exchange_keys
        ),
        "issue_count": issues,
    }


def synchronise_live_positions(
    *,
    exchange_positions: list[dict] | None,
    reconcile_function: Callable[
        [list[dict]],
        dict,
    ] = reconcile_closed_positions,
    sync_function: Callable[..., dict] = (
        sync_cycle_state
    ),
) -> dict:
    """Synchronise one verified Binance position snapshot.

    Order of operations is intentional:

    1. Audit the pre-sync state.
    2. Reconcile disappeared local OPEN positions into completed trades.
    3. Upsert current Binance positions into local persistent state.
    4. Audit the post-sync state.

    This prevents ``sync_cycle_state`` from closing local rows before the
    lifecycle journal has captured exact/fallback close information.
    """
    if not isinstance(
        exchange_positions,
        list,
    ):
        return {
            "status": "blocked",
            "version": "v27",
            "reason": (
                "Exchange positions must be "
                "a verified list"
            ),
            "mutation_performed": False,
            "execution_submitted": False,
            "errors": [
                "Invalid exchange-position snapshot"
            ],
        }

    local_before = list_position_states(
        status="OPEN"
    )
    audit_before = (
        build_position_consistency_audit(
            exchange_positions=(
                exchange_positions
            ),
            local_open_states=local_before,
        )
    )

    errors: list[str] = []

    try:
        lifecycle = reconcile_function(
            exchange_positions
        )
    except Exception as error:
        lifecycle = {
            "status": "error",
            "version": "v25",
            "closed_positions_detected": 0,
            "completed_trades": [],
            "errors": [str(error)],
        }
        errors.append(
            "Position lifecycle reconciliation "
            f"failed: {error}"
        )

    try:
        persistent_sync = sync_function(
            open_positions=(
                exchange_positions
            ),
            partial_take_profit_results=[],
            break_even_results=[],
            trailing_stop_results=[],
            protection_results=[],
        )
    except Exception as error:
        persistent_sync = {
            "status": "error",
            "errors": [str(error)],
        }
        errors.append(
            "Persistent position-state sync "
            f"failed: {error}"
        )

    local_after = list_position_states(
        status="OPEN"
    )
    audit_after = (
        build_position_consistency_audit(
            exchange_positions=(
                exchange_positions
            ),
            local_open_states=local_after,
        )
    )

    try:
        record_event(
            "LIVE_POSITION_SYNC",
            {
                "audit_before": audit_before,
                "audit_after": audit_after,
                "lifecycle_status": (
                    lifecycle.get("status")
                ),
                "persistent_sync_status": (
                    persistent_sync.get(
                        "status"
                    )
                ),
                "timestamp": datetime.now(
                    timezone.utc
                ).isoformat(
                    timespec="milliseconds"
                ),
            },
        )
    except Exception as error:
        errors.append(
            "Position sync event could not "
            f"be recorded: {error}"
        )

    return {
        "status": (
            "success"
            if not errors
            and audit_after.get(
                "status"
            )
            == "consistent"
            else "partial"
            if audit_after.get(
                "status"
            )
            == "consistent"
            else "drift_detected"
        ),
        "version": "v27",
        "source_of_truth": "BINANCE_TESTNET",
        "mutation_performed": True,
        "execution_submitted": False,
        "exchange_position_count": len(
            exchange_positions
        ),
        "audit_before": audit_before,
        "position_lifecycle": lifecycle,
        "persistent_trade_state": (
            persistent_sync
        ),
        "audit_after": audit_after,
        "errors": errors,
    }
