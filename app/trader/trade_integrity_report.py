"""TitanAI Trade Integrity Report v36."""
from __future__ import annotations

from app.trader.execution_consistency_engine import (
    evaluate_execution_consistency,
)
from app.trader.pnl_reconciliation_engine import (
    reconcile_completed_trades,
)
from app.trader.restart_integrity_checker import (
    check_restart_integrity,
)


def build_trade_integrity_report(
    *,
    exchange_positions: list[dict] | None,
    exchange_orders: list[dict] | None,
    execution: dict | None,
    completed_trades: list[dict] | None,
    local_open_states: list[dict] | None = None,
) -> dict:
    execution_consistency = evaluate_execution_consistency(execution)
    restart_integrity = check_restart_integrity(
        exchange_positions=exchange_positions,
        exchange_orders=exchange_orders,
        local_open_states=local_open_states,
        completed_trades=completed_trades,
    )
    pnl_reconciliation = reconcile_completed_trades(completed_trades)

    checks = {
        "execution_consistency": execution_consistency["consistent"],
        "restart_integrity": restart_integrity["restart_safe"],
        "pnl_reconciliation": pnl_reconciliation["mismatch_count"] == 0,
    }
    passed = sum(1 for value in checks.values() if value)
    score = round(passed / len(checks) * 100.0, 2)

    return {
        "status": "healthy" if passed == len(checks) else "review_required",
        "version": "v36",
        "integrity_score_percent": score,
        "checks": checks,
        "execution_consistency": execution_consistency,
        "restart_integrity": restart_integrity,
        "pnl_reconciliation": pnl_reconciliation,
        "execution_submitted": False,
        "read_only": True,
        "advisory_only": True,
    }
