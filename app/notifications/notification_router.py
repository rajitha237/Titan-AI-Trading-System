"""TitanAI Notification Router v32."""

from __future__ import annotations

from typing import Callable

from app.notifications.notification_models import (
    build_notification,
)
from app.notifications.notification_history import (
    save_notification,
)
from app.notifications.telegram_notifier import (
    send_telegram_notification,
)


def _safe_dict(value) -> dict:
    return value if isinstance(value, dict) else {}


def _safe_list(value) -> list:
    return value if isinstance(value, list) else []


def derive_notifications(
    result: dict | None,
) -> list[dict]:
    result = _safe_dict(result)
    cycle_id = result.get("cycle_id")
    symbol = result.get("symbol")
    execution = _safe_dict(
        result.get("execution")
    )
    watchdog = _safe_dict(
        result.get("execution_watchdog")
    )
    health = _safe_dict(
        watchdog.get("exchange_health")
    )
    lifecycle = _safe_dict(
        result.get("position_lifecycle")
    )
    recovery = _safe_dict(
        result.get("order_recovery")
    )
    sync = _safe_dict(
        result.get("live_position_sync")
    )
    risk = _safe_dict(
        result.get("risk_plan")
    )
    daily_risk = _safe_dict(
        result.get("daily_risk")
    )
    notifications: list[dict] = []

    def add(
        event_type: str,
        severity: str,
        title: str,
        message: str,
        data: dict | None = None,
    ) -> None:
        notifications.append(
            build_notification(
                event_type=event_type,
                severity=severity,
                title=title,
                message=message,
                cycle_id=cycle_id,
                symbol=symbol,
                data=data,
            )
        )

    if str(
        result.get("status", "")
    ).lower() == "error":
        add(
            "SYSTEM_ERROR",
            "CRITICAL",
            "Runner Error",
            str(
                result.get(
                    "reason",
                    "TitanAI runner failed",
                )
            ),
            {
                "error": result.get("error"),
            },
        )

    if execution.get("submitted") is True:
        add(
            "TRADE_SUBMITTED",
            "INFO",
            "Trade Submitted",
            (
                f"TitanAI submitted a "
                f"{execution.get('decision') or 'trade'}"
                " order."
            ),
            {
                "execution": execution,
            },
        )

    closed_count = int(
        lifecycle.get(
            "closed_positions_detected",
            0,
        )
        or 0
    )
    if closed_count > 0:
        add(
            "POSITION_CLOSED",
            "INFO",
            "Position Closed",
            (
                f"{closed_count} closed position(s) "
                "were reconciled."
            ),
            {
                "completed_trades": _safe_list(
                    lifecycle.get(
                        "completed_trades"
                    )
                ),
            },
        )

    if watchdog.get("allowed") is False:
        add(
            "WATCHDOG_BLOCKED",
            "CRITICAL",
            "Execution Watchdog Block",
            (
                "The execution watchdog blocked "
                "the runner cycle."
            ),
            {
                "block_reasons": _safe_list(
                    watchdog.get(
                        "block_reasons"
                    )
                ),
                "circuit_breaker": _safe_dict(
                    watchdog.get(
                        "circuit_breaker"
                    )
                ),
            },
        )

    if (
        health
        and health.get("healthy")
        is False
    ):
        add(
            "EXCHANGE_UNHEALTHY",
            "CRITICAL",
            "Exchange Health Degraded",
            (
                "Binance Testnet health checks "
                "did not pass."
            ),
            {
                "exchange_health": health,
            },
        )

    unresolved = _safe_list(
        recovery.get(
            "unresolved_terminal_orders"
        )
    )
    if unresolved:
        add(
            "ORDER_RECOVERY_REVIEW",
            "WARNING",
            "Order Recovery Review",
            (
                f"{len(unresolved)} order(s) "
                "require terminal-status review."
            ),
            {
                "orders": unresolved,
            },
        )

    if str(
        sync.get("status", "")
    ).lower() == "drift_detected":
        add(
            "POSITION_SYNC_DRIFT",
            "CRITICAL",
            "Position State Drift",
            (
                "Exchange and local position "
                "state are inconsistent."
            ),
            {
                "audit_after": _safe_dict(
                    sync.get("audit_after")
                ),
            },
        )

    risk_blocked = (
        daily_risk.get("allowed")
        is False
        or (
            risk
            and risk.get(
                "execution_allowed"
            )
            is False
        )
    )
    if risk_blocked:
        add(
            "RISK_BLOCKED",
            "WARNING",
            "Risk Gate Block",
            (
                "A risk control blocked "
                "trade execution."
            ),
            {
                "daily_risk": daily_risk,
                "risk_plan": risk,
            },
        )

    learning_status = str(
        result.get(
            "learning_status",
            "",
        )
    ).upper()
    if learning_status in {
        "SUPPORT",
        "OPPOSITION",
        "CALIBRATED",
    }:
        add(
            "LEARNING_MILESTONE",
            "INFO",
            "Learning Milestone",
            (
                "TitanAI learning evidence "
                f"reached {learning_status}."
            ),
            {
                "learning_adjustment": (
                    result.get(
                        "learning_adjustment"
                    )
                ),
            },
        )

    return notifications


def route_notifications(
    result: dict | None,
    *,
    history_function: Callable = (
        save_notification
    ),
    telegram_function: Callable = (
        send_telegram_notification
    ),
) -> dict:
    notifications = (
        derive_notifications(result)
    )
    routed = []
    errors: list[str] = []

    for notification in notifications:
        telegram_result = {
            "status": "not_attempted",
            "sent": False,
        }

        try:
            telegram_result = (
                telegram_function(
                    notification
                )
            )
        except Exception as error:
            telegram_result = {
                "status": "failed",
                "sent": False,
                "reason": str(error),
            }
            errors.append(
                "Telegram notifier failed: "
                f"{error}"
            )

        telegram_status = str(
            telegram_result.get(
                "status",
                "unknown",
            )
        )

        try:
            history = history_function(
                notification,
                delivery_status=(
                    "delivered"
                    if telegram_result.get(
                        "sent"
                    )
                    else "stored_only"
                ),
                telegram_status=(
                    telegram_status
                ),
            )
        except Exception as error:
            history = {
                "status": "error",
                "error": str(error),
            }
            errors.append(
                "Notification history failed: "
                f"{error}"
            )

        routed.append(
            {
                "notification": notification,
                "telegram": telegram_result,
                "history": history,
            }
        )

    return {
        "status": (
            "success"
            if not errors
            else "partial"
        ),
        "version": "v32",
        "event_count": len(
            notifications
        ),
        "stored_count": sum(
            1
            for item in routed
            if "notification_id"
            in _safe_dict(
                item.get("history")
            )
        ),
        "telegram_sent_count": sum(
            1
            for item in routed
            if _safe_dict(
                item.get("telegram")
            ).get("sent")
            is True
        ),
        "events": routed,
        "errors": errors,
        "non_blocking": True,
    }
