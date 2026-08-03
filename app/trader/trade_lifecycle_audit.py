"""TitanAI Trade Lifecycle Audit v36.

Read-only consistency checks across exchange snapshots, persistent open-position
state, completed trades, and protection metadata.
"""
from __future__ import annotations

from typing import Any

from app.trader.persistent_trade_state import (
    list_completed_trades,
    list_position_states,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return default
        return number
    except (TypeError, ValueError):
        return default


def _exchange_position_key(position: dict) -> tuple[str, str] | None:
    if not isinstance(position, dict):
        return None
    symbol = str(position.get("symbol", "")).upper()
    amount = _safe_float(
        position.get(
            "positionAmt",
            position.get("position_amount", 0.0),
        )
    )
    if not symbol or amount == 0:
        return None
    return symbol, "BUY" if amount > 0 else "SELL"


def audit_trade_lifecycle(
    *,
    exchange_positions: list[dict] | None,
    exchange_orders: list[dict] | None,
    local_open_states: list[dict] | None = None,
    completed_trades: list[dict] | None = None,
) -> dict:
    exchange_positions = (
        exchange_positions if isinstance(exchange_positions, list) else []
    )
    exchange_orders = exchange_orders if isinstance(exchange_orders, list) else []
    local_open_states = (
        list_position_states(status="OPEN")
        if local_open_states is None
        else local_open_states
    )
    completed_trades = (
        list_completed_trades(limit=1000)
        if completed_trades is None
        else completed_trades
    )

    exchange_keys = {
        key
        for key in (
            _exchange_position_key(position)
            for position in exchange_positions
        )
        if key is not None
    }
    local_keys = {
        (
            str(state.get("symbol", "")).upper(),
            str(state.get("side", "")).upper(),
        )
        for state in local_open_states
        if isinstance(state, dict)
    }

    missing_local = sorted(exchange_keys - local_keys)
    missing_exchange = sorted(local_keys - exchange_keys)

    duplicate_trade_ids = []
    seen_trade_ids = set()
    for trade in completed_trades:
        if not isinstance(trade, dict):
            continue
        trade_id = str(trade.get("trade_id", ""))
        if not trade_id:
            continue
        if trade_id in seen_trade_ids:
            duplicate_trade_ids.append(trade_id)
        seen_trade_ids.add(trade_id)

    unprotected_states = []
    for state in local_open_states:
        if not isinstance(state, dict):
            continue
        if not bool(state.get("protection_verified", False)):
            unprotected_states.append(
                {
                    "position_key": state.get("position_key"),
                    "symbol": state.get("symbol"),
                    "side": state.get("side"),
                }
            )

    orphan_reduce_only_orders = []
    for order in exchange_orders:
        if not isinstance(order, dict):
            continue
        reduce_only = bool(
            order.get("reduceOnly", order.get("reduce_only", False))
        )
        symbol = str(order.get("symbol", "")).upper()
        if reduce_only and not any(key[0] == symbol for key in exchange_keys):
            orphan_reduce_only_orders.append(
                {
                    "symbol": symbol,
                    "order_id": order.get("orderId", order.get("order_id")),
                    "type": order.get("type"),
                }
            )

    issues = {
        "exchange_positions_missing_local_state": [
            {"symbol": symbol, "side": side}
            for symbol, side in missing_local
        ],
        "local_states_missing_exchange_position": [
            {"symbol": symbol, "side": side}
            for symbol, side in missing_exchange
        ],
        "unprotected_local_positions": unprotected_states,
        "orphan_reduce_only_orders": orphan_reduce_only_orders,
        "duplicate_completed_trade_ids": sorted(set(duplicate_trade_ids)),
    }
    issue_count = sum(len(value) for value in issues.values())

    return {
        "status": "consistent" if issue_count == 0 else "review_required",
        "version": "v36",
        "issue_count": issue_count,
        "issues": issues,
        "counts": {
            "exchange_open_positions": len(exchange_keys),
            "local_open_states": len(local_keys),
            "exchange_open_orders": len(exchange_orders),
            "completed_trades": len(completed_trades),
        },
        "read_only": True,
    }
