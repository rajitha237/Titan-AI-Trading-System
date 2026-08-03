"""TitanAI Live Position Manager v26.

This module coordinates existing position-management components without
duplicating exchange-side logic. It is safe to call once per runner cycle.
"""

from __future__ import annotations

from typing import Any

from app.trader.break_even_manager import (
    manage_break_even_for_open_positions,
)
from app.trader.partial_take_profit_manager import (
    manage_partial_take_profit_for_open_positions,
)
from app.trader.trailing_stop_manager import (
    manage_trailing_stop_for_open_positions,
)
from app.trader.sl_tp_manager import (
    inspect_position_protection,
)
from app.trader.persistent_trade_state import (
    sync_cycle_state,
)


DEFAULT_PARTIAL_TP_STAGES = (
    {
        "name": "TP1",
        "trigger_percent": 0.50,
        "close_fraction": 0.25,
    },
    {
        "name": "TP2",
        "trigger_percent": 1.00,
        "close_fraction": 0.25,
    },
    {
        "name": "TP3",
        "trigger_percent": 1.50,
        "close_fraction": 0.25,
    },
)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)
        if result != result:
            return default
        if result in {
            float("inf"),
            float("-inf"),
        }:
            return default
        return result
    except (TypeError, ValueError):
        return default


def _is_open_position(position: Any) -> bool:
    if not isinstance(position, dict):
        return False

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

    return abs(amount) > 0.0


def _position_summary(position: dict) -> dict:
    amount = _safe_float(
        position.get(
            "positionAmt",
            position.get("position_amount", 0.0),
        )
    )

    return {
        "symbol": str(
            position.get("symbol", "")
        ).upper(),
        "side": (
            "BUY"
            if amount > 0
            else "SELL"
            if amount < 0
            else "NONE"
        ),
        "quantity": abs(amount),
        "entry_price": _safe_float(
            position.get(
                "entryPrice",
                position.get("entry_price"),
            )
        ),
        "mark_price": _safe_float(
            position.get(
                "markPrice",
                position.get("mark_price"),
            )
        ),
        "unrealized_profit": _safe_float(
            position.get(
                "unRealizedProfit",
                position.get("unrealized_profit"),
            )
        ),
    }


def manage_live_positions(
    *,
    positions: list[dict] | None,
    partial_tp_stages: tuple[dict, ...] = (
        DEFAULT_PARTIAL_TP_STAGES
    ),
    partial_tp_runner_fraction: float = 0.25,
    break_even_trigger_percent: float = 0.50,
    break_even_buffer_percent: float = 0.10,
    trailing_activation_percent: float = 0.75,
    trailing_distance_percent: float = 0.30,
    trailing_minimum_move_percent: float = 0.10,
) -> dict:
    """Manage all currently open positions and persist management state."""
    active_positions = [
        position
        for position in (positions or [])
        if _is_open_position(position)
    ]

    if not active_positions:
        return {
            "status": "ready",
            "version": "v26",
            "active_position_count": 0,
            "new_entry_allowed": True,
            "reason": "No active positions",
            "positions": [],
            "partial_take_profit": [],
            "break_even": [],
            "trailing_stop": [],
            "protection": [],
            "persistent_state": {
                "status": "not_required",
            },
            "errors": [],
        }

    errors: list[str] = []

    try:
        partial_results = (
            manage_partial_take_profit_for_open_positions(
                positions=active_positions,
                stages=partial_tp_stages,
                runner_fraction=partial_tp_runner_fraction,
            )
        )
    except Exception as error:
        partial_results = []
        errors.append(
            f"Partial take-profit manager failed: {error}"
        )

    try:
        break_even_results = (
            manage_break_even_for_open_positions(
                positions=active_positions,
                trigger_percent=break_even_trigger_percent,
                buffer_percent=break_even_buffer_percent,
            )
        )
    except Exception as error:
        break_even_results = []
        errors.append(
            f"Break-even manager failed: {error}"
        )

    try:
        trailing_results = (
            manage_trailing_stop_for_open_positions(
                positions=active_positions,
                activation_percent=trailing_activation_percent,
                trailing_distance_percent=trailing_distance_percent,
                minimum_move_percent=trailing_minimum_move_percent,
            )
        )
    except Exception as error:
        trailing_results = []
        errors.append(
            f"Trailing-stop manager failed: {error}"
        )

    protection_results = []

    for position in active_positions:
        try:
            protection_results.append(
                inspect_position_protection(
                    symbol=str(
                        position.get("symbol", "")
                    ).upper()
                )
            )
        except Exception as error:
            errors.append(
                "Protection inspection failed for "
                f"{position.get('symbol')}: {error}"
            )

    try:
        persistent_state = sync_cycle_state(
            open_positions=active_positions,
            partial_take_profit_results=partial_results,
            break_even_results=break_even_results,
            trailing_stop_results=trailing_results,
            protection_results=protection_results,
        )
    except Exception as error:
        persistent_state = {
            "status": "error",
            "errors": [str(error)],
        }
        errors.append(
            f"Persistent state sync failed: {error}"
        )

    protected = bool(protection_results) and all(
        isinstance(item, dict)
        and item.get("protected") is True
        for item in protection_results
    )

    return {
        "status": (
            "managed"
            if not errors
            else "degraded"
        ),
        "version": "v26",
        "active_position_count": len(
            active_positions
        ),
        "new_entry_allowed": False,
        "all_positions_protected": protected,
        "reason": (
            "Existing position management completed"
            if not errors
            else "Position management completed with errors"
        ),
        "positions": [
            _position_summary(position)
            for position in active_positions
        ],
        "partial_take_profit": partial_results,
        "break_even": break_even_results,
        "trailing_stop": trailing_results,
        "protection": protection_results,
        "persistent_state": persistent_state,
        "errors": errors,
    }
