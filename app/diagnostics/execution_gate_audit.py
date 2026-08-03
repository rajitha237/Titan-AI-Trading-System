"""Execution-gate audit helpers for TitanAI."""
from __future__ import annotations
from typing import Any


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def build_execution_gate_audit(
    *,
    final_decision: dict | None,
    validation: dict | None,
    trade_quality: dict | None,
    confirmation: dict | None,
    risk_plan: dict | None,
    trade_plan: dict | None,
) -> dict:
    decision = str(
        _mapping(final_decision).get("decision", "HOLD")
    ).upper()
    validation = _mapping(validation)
    trade_quality = _mapping(trade_quality)
    confirmation = _mapping(confirmation)
    risk_plan = _mapping(risk_plan)
    trade_plan = _mapping(trade_plan)

    causal = []
    cascaded = []

    if decision not in {"BUY", "SELL"}:
        causal.append(f"Final decision is {decision}")

    if validation.get("allowed") is not True:
        causal.append(
            "Validator rejected: "
            + str(validation.get("reason", "unknown reason"))
        )

    if trade_quality.get("passed") is not True:
        details = ", ".join(
            str(item)
            for item in trade_quality.get("primary_blockers", [])
            if item
        )
        causal.append(
            "Trade Quality rejected"
            + (f": {details}" if details else "")
        )

    if confirmation.get("passed") is not True:
        causal.append(
            "Confirmation rejected: "
            + str(confirmation.get("decision", "UNKNOWN"))
        )

    if risk_plan.get("approved") is not True:
        cascaded.append("Risk plan blocked after upstream rejection")

    if trade_plan.get("ready") is not True:
        cascaded.append("Trade plan unavailable after upstream rejection")

    return {
        "status": "ready",
        "version": "execution_gate_audit_v1",
        "causal_blockers": list(dict.fromkeys(causal)),
        "cascaded_blockers": list(dict.fromkeys(cascaded)),
        "first_causal_blocker": causal[0] if causal else None,
        "execution_ready": not causal and not cascaded,
        "diagnostics_only": True,
    }
