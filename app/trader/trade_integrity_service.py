"""TitanAI Non-Blocking Trade Integrity Service v36."""
from __future__ import annotations

from app.trader.persistent_trade_state import (
    list_completed_trades,
    list_position_states,
)
from app.trader.trade_integrity_report import (
    build_trade_integrity_report,
)


def build_trade_integrity_snapshot(result: dict | None) -> dict:
    result = result if isinstance(result, dict) else {}
    try:
        exchange_positions = (
            result.get("open_positions")
            if isinstance(result.get("open_positions"), list)
            else []
        )
        order_recovery = (
            result.get("order_recovery")
            if isinstance(result.get("order_recovery"), dict)
            else {}
        )
        exchange_orders = (
            order_recovery.get("exchange_orders")
            if isinstance(order_recovery.get("exchange_orders"), list)
            else []
        )
        lifecycle = (
            result.get("position_lifecycle")
            if isinstance(result.get("position_lifecycle"), dict)
            else {}
        )
        completed = (
            lifecycle.get("completed_trades")
            if isinstance(lifecycle.get("completed_trades"), list)
            else []
        )
        if not completed:
            completed = list_completed_trades(limit=1000)

        report = build_trade_integrity_report(
            exchange_positions=exchange_positions,
            exchange_orders=exchange_orders,
            execution=result.get("execution"),
            completed_trades=completed,
            local_open_states=list_position_states(status="OPEN"),
        )
        return {
            "status": "success",
            "version": "v36",
            "report": report,
            "non_blocking": True,
            "read_only": True,
        }
    except Exception as error:
        return {
            "status": "error",
            "version": "v36",
            "report": None,
            "errors": [str(error)],
            "non_blocking": True,
            "read_only": True,
        }
