"""Read-only TitanAI monitoring dashboard v31."""
from __future__ import annotations
from datetime import datetime, timezone
from app.dashboard.dashboard_models import (
    normalise_status,
    safe_dict,
    safe_float,
    safe_list,
    section,
)

_BAD = {"blocked", "error", "unsafe", "drift_detected", "critical"}
_WARN = {"partial", "review_required", "degraded", "watch"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _health(statuses: list) -> str:
    values = {normalise_status(item) for item in statuses if item is not None}
    if values & _BAD:
        return "critical"
    if values & _WARN:
        return "degraded"
    if values:
        return "healthy"
    return "unknown"


def build_system_dashboard(result: dict | None) -> dict:
    result = safe_dict(result)
    sync = safe_dict(result.get("live_position_sync"))
    recovery = safe_dict(result.get("order_recovery"))
    watchdog = safe_dict(result.get("execution_watchdog"))
    exchange = safe_dict(watchdog.get("exchange_health"))
    service = safe_dict(result.get("service_state"))
    lifecycle = safe_dict(result.get("position_lifecycle"))
    execution = safe_dict(result.get("execution"))
    risk = safe_dict(result.get("risk_plan"))
    sizing = safe_dict(result.get("dynamic_sizing"))
    exposure = safe_dict(result.get("portfolio_exposure"))
    daily_risk = safe_dict(result.get("daily_risk"))
    learning = safe_dict(result.get("learning_dashboard"))
    learning_diag = safe_dict(result.get("learning_diagnostics"))
    candidate = safe_dict(result.get("best_setup"))
    scan = safe_dict(result.get("scan"))
    if not candidate:
        candidate = safe_dict(scan.get("best_setup"))
    ai_score = safe_dict(result.get("ai_score") or candidate.get("ai_score"))
    decision = safe_dict(result.get("final_decision") or candidate.get("final_decision"))
    confidence = safe_dict(result.get("confidence"))
    position_audit = safe_dict(sync.get("audit_after"))
    order_audit = safe_dict(recovery.get("audit_after"))
    positions = safe_list(result.get("open_positions"))
    symbol = str(result.get("symbol") or candidate.get("symbol") or "").upper()
    overall = _health([
        result.get("status"),
        sync.get("status"),
        recovery.get("status"),
        watchdog.get("status"),
        exchange.get("status"),
    ])

    return {
        "status": "ready",
        "version": "v31",
        "generated_at": _now(),
        "read_only": True,
        "diagnostics_only": True,
        "overall_health": overall,
        "system": section(overall, "TitanAI operational snapshot", {
            "runner_status": result.get("status"),
            "mode": result.get("mode") or execution.get("mode"),
            "cycle_id": result.get("cycle_id") or service.get("cycle_id"),
            "started_at": result.get("started_at") or service.get("started_at"),
            "finished_at": result.get("finished_at") or service.get("completed_at"),
        }),
        "exchange": section(exchange.get("status"), "Binance Testnet health", {
            "healthy": exchange.get("healthy"),
            "latency_ms": safe_float(exchange.get("latency_ms")),
            "clock_offset_ms": safe_float(exchange.get("clock_offset_ms")),
            "checks": safe_dict(exchange.get("checks")),
        }, safe_list(exchange.get("errors"))),
        "watchdog": section(watchdog.get("status"), "Pre-scan execution gate", {
            "allowed": watchdog.get("allowed"),
            "circuit_breaker": safe_dict(watchdog.get("circuit_breaker")),
            "block_reasons": safe_list(watchdog.get("block_reasons")),
        }),
        "service": section(service.get("status"), "Persistent service state", service),
        "positions": section(sync.get("status"), f"{len(positions)} active position(s)", {
            "count": result.get("open_positions_count", len(positions)),
            "positions": positions,
            "consistency_status": position_audit.get("status"),
            "issue_count": position_audit.get("issue_count", 0),
            "closed_positions_detected": lifecycle.get("closed_positions_detected", 0),
        }, safe_list(lifecycle.get("errors"))),
        "orders": section(recovery.get("status"), "Order recovery state", {
            "exchange_open_order_count": recovery.get(
                "exchange_open_order_count",
                order_audit.get("exchange_open_order_count", 0),
            ),
            "consistency_status": order_audit.get("status"),
            "issue_count": order_audit.get("issue_count", 0),
            "unresolved_terminal_orders": safe_list(recovery.get("unresolved_terminal_orders")),
            "orders_submitted": recovery.get("orders_submitted", 0),
            "orders_cancelled": recovery.get("orders_cancelled", 0),
        }, safe_list(recovery.get("errors"))),
        "risk": section(
            "ready" if risk.get("approved") else daily_risk.get("status"),
            "Risk, sizing, and exposure",
            {
                "daily_risk_allowed": daily_risk.get("allowed"),
                "risk_approved": risk.get("approved"),
                "execution_allowed": risk.get("execution_allowed"),
                "risk_percent": sizing.get("effective_risk_percent"),
                "position_size_usdt": risk.get(
                    "position_size_usdt",
                    sizing.get("recommended_position_usdt"),
                ),
                "portfolio_exposure_allowed": exposure.get("allowed"),
                "current_exposure_usdt": exposure.get("current_exposure_usdt"),
                "projected_exposure_usdt": exposure.get("projected_exposure_usdt"),
                "block_reasons": safe_list(risk.get("block_reasons")),
            },
        ),
        "ai": section("ready" if symbol else "unknown", "Selected AI candidate", {
            "selected_symbol": symbol or None,
            "price": safe_float(result.get("price") or candidate.get("price")),
            "signal": ai_score.get("signal"),
            "ai_score": safe_float(ai_score.get("score")),
            "confidence_score": confidence.get(
                "adjusted_confidence_score",
                confidence.get("confidence_score", confidence.get("score")),
            ),
            "final_decision": decision.get("decision"),
            "strategy": safe_dict(result.get("optimized_strategy")),
            "selected_candidate_rank": result.get("selected_candidate_rank"),
            "candidates_evaluated": result.get("candidates_evaluated", 0),
        }),
        "learning": section(
            result.get("learning_status") or learning_diag.get("learning_status"),
            "Self-learning diagnostics",
            {
                "learning_status": result.get("learning_status") or learning_diag.get("learning_status"),
                "learning_adjustment": result.get(
                    "learning_adjustment",
                    learning_diag.get("learning_adjustment", 0.0),
                ),
                "pattern_adjustment": learning_diag.get("pattern_adjustment", 0.0),
                "dashboard": learning,
                "diagnostics": learning_diag,
            },
        ),
        "execution": section(execution.get("status"), "Latest execution decision", {
            "submitted": bool(execution.get("submitted", False)),
            "mode": execution.get("mode"),
            "reason": execution.get("reason"),
            "decision": execution.get("decision") or decision.get("decision"),
            "protected": execution.get("protected"),
            "block_reasons": safe_list(
                execution.get("block_reasons") or result.get("execution_blocks")
            ),
        }),
    }
