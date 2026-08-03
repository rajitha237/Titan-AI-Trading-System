"""TitanAI Completed-Trade PnL Reconciliation v36."""
from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in {float("inf"), float("-inf")}:
            return default
        return number
    except (TypeError, ValueError):
        return default


def reconcile_completed_trade_pnl(
    trade: dict | None,
    *,
    tolerance: float = 1e-8,
) -> dict:
    trade = trade if isinstance(trade, dict) else {}
    metadata = trade.get("metadata") if isinstance(trade.get("metadata"), dict) else {}
    fills = metadata.get("closing_fills") if isinstance(metadata.get("closing_fills"), list) else []

    reported_gross = _safe_float(trade.get("gross_pnl"))
    reported_fees = abs(_safe_float(trade.get("fees")))
    reported_net = _safe_float(trade.get("net_pnl"))

    fill_gross = sum(_safe_float(item.get("realizedPnl")) for item in fills if isinstance(item, dict))
    fill_fees = sum(
        abs(_safe_float(item.get("commission")))
        for item in fills
        if isinstance(item, dict)
    )
    fill_net = fill_gross - fill_fees

    exact_data = bool(metadata.get("exact_binance_data", False))
    issues = []

    if abs((reported_gross - reported_fees) - reported_net) > tolerance:
        issues.append("Reported net PnL does not equal gross PnL minus fees")

    if exact_data and fills:
        if abs(fill_gross - reported_gross) > tolerance:
            issues.append("Closing-fill realized PnL differs from reported gross PnL")
        if abs(fill_fees - reported_fees) > tolerance:
            issues.append("Closing-fill commissions differ from reported fees")
        if abs(fill_net - reported_net) > tolerance:
            issues.append("Closing-fill net PnL differs from reported net PnL")

    return {
        "status": "reconciled" if not issues else "mismatch",
        "version": "v36",
        "reconciled": not issues,
        "exact_binance_data": exact_data,
        "issues": issues,
        "reported": {
            "gross_pnl": reported_gross,
            "fees": reported_fees,
            "net_pnl": reported_net,
        },
        "calculated_from_closing_fills": {
            "gross_pnl": fill_gross,
            "fees": fill_fees,
            "net_pnl": fill_net,
            "fill_count": len(fills),
        },
        "read_only": True,
    }


def reconcile_completed_trades(
    trades: list[dict] | None,
) -> dict:
    results = [
        reconcile_completed_trade_pnl(trade)
        for trade in (trades or [])
        if isinstance(trade, dict)
    ]
    mismatches = [result for result in results if not result["reconciled"]]
    return {
        "status": "success" if not mismatches else "review_required",
        "version": "v36",
        "trade_count": len(results),
        "mismatch_count": len(mismatches),
        "results": results,
        "read_only": True,
    }
