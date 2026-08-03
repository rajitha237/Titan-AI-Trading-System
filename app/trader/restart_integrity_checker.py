"""TitanAI Restart Integrity Checker v36."""
from __future__ import annotations

from app.trader.trade_lifecycle_audit import audit_trade_lifecycle


def check_restart_integrity(
    *,
    exchange_positions: list[dict] | None,
    exchange_orders: list[dict] | None,
    local_open_states: list[dict] | None = None,
    completed_trades: list[dict] | None = None,
) -> dict:
    audit = audit_trade_lifecycle(
        exchange_positions=exchange_positions,
        exchange_orders=exchange_orders,
        local_open_states=local_open_states,
        completed_trades=completed_trades,
    )

    critical_issue_names = {
        "exchange_positions_missing_local_state",
        "local_states_missing_exchange_position",
        "duplicate_completed_trade_ids",
    }
    critical_issues = {
        name: values
        for name, values in audit["issues"].items()
        if name in critical_issue_names and values
    }

    ready = not critical_issues

    return {
        "status": "ready" if ready else "blocked",
        "version": "v36",
        "restart_safe": ready,
        "critical_issues": critical_issues,
        "audit": audit,
        "execution_submitted": False,
        "read_only": True,
    }
