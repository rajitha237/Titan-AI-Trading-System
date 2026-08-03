"""TitanAI Execution Consistency Engine v36."""
from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if value == value and abs(value) != float("inf") else default
    except (TypeError, ValueError):
        return default


def evaluate_execution_consistency(execution: dict | None) -> dict:
    execution = execution if isinstance(execution, dict) else {}
    verification = (
        execution.get("verification")
        if isinstance(execution.get("verification"), dict)
        else {}
    )

    submitted = execution.get("submitted") is True
    filled = verification.get("filled") is True
    verified = verification.get("verified") is True
    status = str(execution.get("status", "")).lower()
    order_status = str(
        verification.get("order_status", execution.get("order_status", "UNKNOWN"))
    ).upper()

    filled_quantity = _safe_float(
        verification.get(
            "filled_quantity",
            execution.get("filled_quantity", 0.0),
        )
    )
    requested_quantity = _safe_float(execution.get("quantity", 0.0))
    average_price = _safe_float(
        verification.get(
            "average_price",
            execution.get("average_fill_price", 0.0),
        )
    )

    issues = []
    if submitted and not verified:
        issues.append("Submitted order was not verified")
    if filled and filled_quantity <= 0:
        issues.append("Filled order has zero filled quantity")
    if filled and average_price <= 0:
        issues.append("Filled order has zero average fill price")
    if status in {"success", "filled"} and not submitted:
        issues.append("Successful execution is marked as not submitted")
    if order_status == "FILLED" and not filled:
        issues.append("Order status FILLED conflicts with verification flags")
    if requested_quantity > 0 and filled_quantity > requested_quantity * 1.000001:
        issues.append("Filled quantity exceeds requested quantity")

    return {
        "status": "consistent" if not issues else "inconsistent",
        "version": "v36",
        "consistent": not issues,
        "issues": issues,
        "submitted": submitted,
        "verified": verified,
        "filled": filled,
        "order_status": order_status,
        "requested_quantity": requested_quantity,
        "filled_quantity": filled_quantity,
        "average_fill_price": average_price,
        "read_only": True,
    }
