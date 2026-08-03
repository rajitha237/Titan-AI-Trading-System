"""TitanAI event-to-Telegram notification manager with deduplication."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.notifications.telegram_service import TelegramService

STATE_FILE = Path(__file__).resolve().parents[1] / "data" / "notification_state.json"


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        if result != result or result in (float("inf"), float("-inf")):
            return default
        return result
    except (TypeError, ValueError):
        return default


def _utc_time() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _read_state() -> dict[str, Any]:
    try:
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {"sent_event_keys": []}


def _write_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temporary.replace(STATE_FILE)


def _event_key(event_type: str, payload: dict[str, Any]) -> str:
    serialised = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:24]
    return f"{event_type}:{digest}"


class NotificationManager:
    def __init__(self, telegram: TelegramService | None = None) -> None:
        self.telegram = telegram or TelegramService()

    async def _send_once(
        self,
        event_type: str,
        payload: dict[str, Any],
        message: str,
    ) -> dict[str, Any]:
        key = _event_key(event_type, payload)
        state = _read_state()
        sent_keys = list(state.get("sent_event_keys", []))

        if key in sent_keys:
            return {"status": "duplicate", "sent": False, "event_key": key}

        result = await self.telegram.send_message(message)
        if result.get("sent") is True:
            sent_keys.append(key)
            state["sent_event_keys"] = sent_keys[-500:]
            state["last_sent_at"] = _utc_time()
            _write_state(state)

        return {**result, "event_key": key}

    async def notify_startup(
        self,
        *,
        execute_trades: bool,
        interval_seconds: float,
    ) -> dict[str, Any]:
        mode = "TESTNET EXECUTION" if execute_trades else "ANALYSIS ONLY"
        payload = {
            "startup_date": datetime.now(timezone.utc).date().isoformat(),
            "mode": mode,
            "interval": interval_seconds,
        }
        message = (
            "🤖 TitanAI started\n\n"
            f"Mode: {mode}\n"
            f"Cycle interval: {interval_seconds:.0f} seconds\n"
            f"Time: {_utc_time()}"
        )
        return await self._send_once("startup", payload, message)

    async def notify_shutdown(self) -> dict[str, Any]:
        payload = {"shutdown_minute": _utc_time()[:16]}
        return await self._send_once(
            "shutdown",
            payload,
            f"🛑 TitanAI stopped\n\nTime: {_utc_time()}",
        )

    async def notify_error(
        self,
        error: str,
        *,
        cycle_number: int | None = None,
    ) -> dict[str, Any]:
        payload = {
            "error": str(error),
            "cycle_number": cycle_number,
            "hour": _utc_time()[:13],
        }
        message = (
            "⚠️ TitanAI system error\n\n"
            f"Cycle: {cycle_number if cycle_number is not None else 'N/A'}\n"
            f"Error: {str(error)[:900]}\n"
            f"Time: {_utc_time()}"
        )
        return await self._send_once("system_error", payload, message)

    async def process_cycle_result(
        self,
        result: dict[str, Any],
        *,
        cycle_number: int,
    ) -> list[dict[str, Any]]:
        notifications: list[dict[str, Any]] = []
        if not isinstance(result, dict):
            return notifications

        execution = result.get("execution") or {}
        execution_status = str(execution.get("status", "")).lower()
        symbol = str(result.get("symbol", "")).upper()
        decision = str(
            (result.get("final_decision") or {}).get("decision", "")
        ).upper()
        confidence_data = result.get("confidence") or {}
        confidence = _safe_float(
            confidence_data.get("confidence", confidence_data.get("score", confidence_data)),
            0.0,
        )

        if execution_status == "protected":
            trade_plan = result.get("trade_plan") or {}
            protection = execution.get("protection") or execution.get("protection_result") or {}
            payload = {
                "symbol": symbol,
                "decision": decision,
                "entry_order_id": execution.get("order_id")
                    or (execution.get("entry") or {}).get("order_id"),
                "entry": execution.get("average_fill_price")
                    or (execution.get("fill") or {}).get("average_fill_price")
                    or trade_plan.get("entry_price"),
            }
            entry = _safe_float(payload["entry"], _safe_float(result.get("price")))
            quantity = _safe_float(
                execution.get("executed_quantity")
                or (execution.get("fill") or {}).get("executed_quantity")
                or result.get("quantity")
            )
            stop_loss = _safe_float(
                protection.get("stop_loss_price")
                or trade_plan.get("stop_loss_price")
            )
            take_profit = _safe_float(
                protection.get("take_profit_price")
                or trade_plan.get("take_profit_price")
            )

            message = (
                "🟢 TitanAI trade protected\n\n"
                f"{decision or 'TRADE'} {symbol}\n"
                f"Entry: {entry:g}\n"
                f"Quantity: {quantity:g}\n"
                f"Stop loss: {stop_loss:g}\n"
                f"Take profit: {take_profit:g}\n"
                f"Confidence: {confidence:g}%\n"
                f"Time: {_utc_time()}"
            )
            notifications.append(
                await self._send_once("trade_protected", payload, message)
            )

        manager_specs = (
            (
                "partial_take_profit_manager",
                "executed",
                "partial_tp",
                "🔵 Partial take-profit executed",
            ),
            (
                "break_even_manager",
                "moved",
                "break_even",
                "🟡 Break-even stop activated",
            ),
            (
                "trailing_stop_manager",
                "moved",
                "trailing_stop",
                "🟣 Trailing stop updated",
            ),
        )

        for manager_key, event_flag, event_type, title in manager_specs:
            manager = result.get(manager_key) or {}
            items = manager.get("results", []) if isinstance(manager, dict) else []
            for item in items if isinstance(items, list) else []:
                if not isinstance(item, dict) or item.get(event_flag) is not True:
                    continue

                item_symbol = str(item.get("symbol", symbol)).upper()
                payload = {
                    "symbol": item_symbol,
                    "event": event_type,
                    "stage": item.get("stage") or item.get("completed_stage"),
                    "order_id": item.get("order_id")
                        or item.get("close_order_id")
                        or item.get("replacement_order_id"),
                    "quantity": item.get("closed_quantity")
                        or item.get("quantity")
                        or item.get("current_quantity"),
                    "price": item.get("execution_price")
                        or item.get("new_stop_price")
                        or item.get("stop_price"),
                }

                details = [title, "", item_symbol]
                if item.get("stage") or item.get("completed_stage"):
                    details.append(
                        f"Stage: {item.get('stage') or item.get('completed_stage')}"
                    )
                if item.get("closed_quantity") is not None:
                    details.append(f"Closed quantity: {item.get('closed_quantity')}")
                if item.get("new_stop_price") is not None:
                    details.append(f"New stop: {item.get('new_stop_price')}")
                if item.get("realised_pnl") is not None:
                    details.append(f"Realised PnL: {item.get('realised_pnl')}")
                details.append(f"Time: {_utc_time()}")

                notifications.append(
                    await self._send_once(
                        event_type,
                        payload,
                        "\n".join(details),
                    )
                )

        protection = result.get("protection_inspection") or {}
        protection_errors = protection.get("errors", []) if isinstance(protection, dict) else []
        for error in protection_errors if isinstance(protection_errors, list) else []:
            notifications.append(
                await self.notify_error(
                    f"Protection inspection: {error}",
                    cycle_number=cycle_number,
                )
            )

        for warning in result.get("warnings", []) or []:
            notifications.append(
                await self.notify_error(
                    f"Warning: {warning}",
                    cycle_number=cycle_number,
                )
            )

        return notifications