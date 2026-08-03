"""
TitanAI Partial Take Profit Manager v2

Closes an open Binance USD-M Futures Testnet position in configurable profit
stages, then resizes exchange-side stop-loss and take-profit protection to the
verified remaining position quantity.

Default plan:
- TP1: at +0.50%, close 25% of the original position
- TP2: at +1.00%, close another 25%
- TP3: at +1.50%, close another 25%
- Final 25% remains for break-even / trailing-stop management

Safety properties:
- Supports BUY and SELL positions
- Executes at most one stage per manager call
- Uses a per-symbol lock to prevent concurrent duplicate closes
- Persists an in-flight stage before submitting a reduce-only close
- Persists completed stages atomically to prevent duplicate closes after restart
- Never intentionally closes the reserved runner quantity
- Verifies the exchange position reduction with retries
- Requires complete SL/TP protection before a partial close
- Cancels only active SL/TP conditional closing orders when resizing protection
- Confirms protection-order cancellation before replacement
- Recreates and verifies protection for the remaining exchange quantity
- Handles truthy string values safely
- Returns structured fail-closed diagnostics instead of crashing the scheduler
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from math import isfinite
from pathlib import Path
from typing import Any, Iterable

from app.exchange.binance_testnet_client import (
    cancel_algo_order,
    close_position,
    format_quantity,
    get_open_orders,
    get_open_positions,
    place_stop_loss_order,
    place_take_profit_order,
)
from app.trader.sl_tp_manager import inspect_position_protection

DEFAULT_STAGES = (
    {"name": "TP1", "trigger_percent": 0.50, "close_fraction": 0.25},
    {"name": "TP2", "trigger_percent": 1.00, "close_fraction": 0.25},
    {"name": "TP3", "trigger_percent": 1.50, "close_fraction": 0.25},
)
DEFAULT_RUNNER_FRACTION = 0.25
DEFAULT_POSITION_VERIFY_ATTEMPTS = 6
DEFAULT_CANCEL_VERIFY_ATTEMPTS = 5
DEFAULT_PROTECTION_VERIFY_ATTEMPTS = 6
DEFAULT_VERIFY_DELAY_SECONDS = 0.35

STATE_FILE = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "partial_take_profit_state.json"
)

STOP_TYPES = {"STOP", "STOP_MARKET"}
TAKE_PROFIT_TYPES = {"TAKE_PROFIT", "TAKE_PROFIT_MARKET"}
ACTIVE_STATUSES = {"NEW", "PARTIALLY_FILLED", "PENDING_NEW"}
FAILED_RESPONSE_STATUSES = {
    "ERROR",
    "FAILED",
    "REJECTED",
    "EXPIRED",
    "CANCELED",
    "CANCELLED",
}

_LOCKS_GUARD = threading.Lock()
_SYMBOL_LOCKS: dict[str, threading.Lock] = {}
_STATE_LOCK = threading.RLock()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if isfinite(number) else default
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "on"}:
            return True
        if normalized in {"false", "0", "no", "n", "off", "", "none", "null"}:
            return False
    return default


def _normalize_symbol(symbol: Any) -> str:
    return str(symbol or "").strip().upper()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip().upper()


def _get_symbol_lock(symbol: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _SYMBOL_LOCKS.get(symbol)
        if lock is None:
            lock = threading.Lock()
            _SYMBOL_LOCKS[symbol] = lock
        return lock


def _position_side(amount: float) -> str:
    if amount > 0:
        return "BUY"
    if amount < 0:
        return "SELL"
    return "NONE"


def _close_side(position_side: str) -> str:
    if position_side == "BUY":
        return "SELL"
    if position_side == "SELL":
        return "BUY"
    return "NONE"


def _state_key(symbol: str, side: str, entry_price: float) -> str:
    # Entry price remains stable across partial reductions in Binance one-way mode.
    return f"{symbol}:{side}:{entry_price:.12g}"


def _empty_state() -> dict:
    return {"version": 2, "positions": {}}


def _load_state_unlocked() -> dict:
    try:
        if not STATE_FILE.exists():
            return _empty_state()
        with STATE_FILE.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return _empty_state()
        positions = data.get("positions")
        if not isinstance(positions, dict):
            data["positions"] = {}
        data["version"] = 2
        return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return _empty_state()


def _load_state() -> dict:
    with _STATE_LOCK:
        return _load_state_unlocked()


def _save_state_unlocked(state: dict) -> None:
    if not isinstance(state, dict):
        raise TypeError("Partial take-profit state must be a dictionary")

    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_path = tempfile.mkstemp(
        prefix="partial_tp_",
        suffix=".json",
        dir=str(STATE_FILE.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, STATE_FILE)
        try:
            directory_fd = os.open(str(STATE_FILE.parent), os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except OSError:
            # Directory fsync is not available on every platform/filesystem.
            pass
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def _save_state(state: dict) -> None:
    with _STATE_LOCK:
        _save_state_unlocked(state)


def _find_position(symbol: str, positions: list | None = None) -> dict | None:
    source = positions if positions is not None else get_open_positions(symbol=symbol)
    if not isinstance(source, list):
        raise TypeError("Open positions response is not a list")

    for position in source:
        if not isinstance(position, dict):
            continue
        if _normalize_symbol(position.get("symbol")) != symbol:
            continue
        if _safe_float(position.get("positionAmt"), 0.0) != 0:
            return position
    return None


def _trigger_price(side: str, entry_price: float, trigger_percent: float) -> float:
    factor = trigger_percent / 100.0
    return (
        entry_price * (1.0 + factor)
        if side == "BUY"
        else entry_price * (1.0 - factor)
    )


def _trigger_reached(side: str, mark_price: float, trigger_price: float) -> bool:
    return mark_price >= trigger_price if side == "BUY" else mark_price <= trigger_price


def _order_type(order: dict) -> str:
    return _normalize_text(order.get("type", order.get("orderType")))


def _order_stop_price(order: dict | None) -> float:
    if not isinstance(order, dict):
        return 0.0
    return _safe_float(
        order.get("stopPrice", order.get("triggerPrice", order.get("price"))),
        0.0,
    )


def _order_id(order: dict | None) -> int | str | None:
    if not isinstance(order, dict):
        return None
    value = order.get("algoId", order.get("orderId"))
    return value if value not in (None, "") else None


def _order_closes_position(order: dict | None) -> bool:
    if not isinstance(order, dict):
        return False
    return _safe_bool(order.get("reduceOnly"), False) or _safe_bool(
        order.get("closePosition"), False
    )


def _is_active_closing_order(order: dict, close_side: str) -> bool:
    return (
        isinstance(order, dict)
        and _normalize_text(order.get("status", "NEW")) in ACTIVE_STATUSES
        and _normalize_text(order.get("side")) == close_side
        and _order_closes_position(order)
    )


def _find_protection_orders(
    orders: Iterable[dict],
    close_side: str,
) -> tuple[list[dict], list[dict]]:
    stops: list[dict] = []
    take_profits: list[dict] = []
    for order in orders or []:
        if not isinstance(order, dict) or not _is_active_closing_order(order, close_side):
            continue
        order_type = _order_type(order)
        if order_type in STOP_TYPES:
            stops.append(order)
        elif order_type in TAKE_PROFIT_TYPES:
            take_profits.append(order)
    return stops, take_profits


def _select_stop_price(orders: list[dict], side: str) -> float:
    prices = [_order_stop_price(order) for order in orders]
    prices = [price for price in prices if price > 0]
    if not prices:
        return 0.0
    return max(prices) if side == "BUY" else min(prices)


def _select_take_profit_price(orders: list[dict], side: str) -> float:
    prices = [_order_stop_price(order) for order in orders]
    prices = [price for price in prices if price > 0]
    if not prices:
        return 0.0
    # Preserve the nearest active target when duplicates already exist.
    return min(prices) if side == "BUY" else max(prices)


def _response_is_accepted(response: Any) -> bool:
    if not isinstance(response, dict) or not response:
        return False
    if response.get("code") not in (None, 0, "0", 200, "200"):
        return False
    status = _normalize_text(response.get("status"))
    if status in FAILED_RESPONSE_STATUSES:
        return False
    if response.get("success") is not None and not _safe_bool(response.get("success")):
        return False
    return True


def _active_order_ids(symbol: str, close_side: str) -> set[str]:
    orders = get_open_orders(symbol=symbol)
    if not isinstance(orders, list):
        raise TypeError("Open orders response is not a list")
    stops, take_profits = _find_protection_orders(orders, close_side)
    return {
        str(order_id)
        for order_id in (_order_id(order) for order in [*stops, *take_profits])
        if order_id is not None
    }


def _cancel_orders_and_verify(
    symbol: str,
    close_side: str,
    orders: Iterable[dict],
    attempts: int = DEFAULT_CANCEL_VERIFY_ATTEMPTS,
    delay_seconds: float = DEFAULT_VERIFY_DELAY_SECONDS,
) -> dict:
    requested_ids: list[str] = []
    cancelled: list[dict] = []
    errors: list[dict] = []

    for order in orders:
        order_id = _order_id(order)
        if order_id is None:
            errors.append({"order": order, "error": "Missing order ID"})
            continue
        requested_ids.append(str(order_id))
        try:
            response = cancel_algo_order(symbol=symbol, order_id=order_id)
            if not _response_is_accepted(response):
                errors.append(
                    {
                        "order_id": order_id,
                        "error": "Cancellation response was not accepted",
                        "response": response,
                    }
                )
            else:
                cancelled.append(response)
        except Exception as error:
            errors.append({"order_id": order_id, "error": str(error)})

    remaining_ids: set[str] = set(requested_ids)
    verification_error = None
    used_attempts = 0
    for attempt in range(1, max(1, attempts) + 1):
        used_attempts = attempt
        try:
            active_ids = _active_order_ids(symbol, close_side)
            remaining_ids = set(requested_ids) & active_ids
            verification_error = None
            if not remaining_ids:
                break
        except Exception as error:
            verification_error = str(error)
        if attempt < attempts:
            time.sleep(max(0.0, delay_seconds))

    verified = bool(requested_ids) and not remaining_ids and verification_error is None
    if not requested_ids:
        verified = True

    return {
        "verified": verified,
        "requested_order_ids": requested_ids,
        "remaining_order_ids": sorted(remaining_ids),
        "cancelled": cancelled,
        "errors": errors,
        "verification_error": verification_error,
        "verification_attempts": used_attempts,
    }


def _verify_protection_with_retry(
    symbol: str,
    stop_price: float,
    take_profit_price: float,
    attempts: int = DEFAULT_PROTECTION_VERIFY_ATTEMPTS,
    delay_seconds: float = DEFAULT_VERIFY_DELAY_SECONDS,
) -> tuple[bool, dict, int]:
    last_result: dict = {
        "status": "error",
        "protected": False,
        "reason": "Protection verification was not attempted",
    }
    used_attempts = 0

    for attempt in range(1, max(1, attempts) + 1):
        used_attempts = attempt
        try:
            result = inspect_position_protection(
                symbol=symbol,
                stop_loss_price=stop_price,
                take_profit_price=take_profit_price,
            )
            last_result = result if isinstance(result, dict) else {
                "status": "error",
                "protected": False,
                "reason": "Protection verification returned an invalid response",
                "response": result,
            }
        except Exception as error:
            last_result = {
                "status": "error",
                "protected": False,
                "reason": "Protection verification failed",
                "error": str(error),
            }

        if last_result.get("protected") is True:
            return True, last_result, used_attempts
        if attempt < attempts:
            time.sleep(max(0.0, delay_seconds))

    return False, last_result, used_attempts


def _create_protection_pair(
    symbol: str,
    side: str,
    quantity: float,
    stop_price: float,
    take_profit_price: float,
) -> dict:
    stop_order = None
    take_profit_order = None
    errors: dict[str, Any] = {}

    try:
        response = place_stop_loss_order(
            symbol=symbol,
            side=side,
            stop_price=stop_price,
            quantity=quantity,
        )
        if _response_is_accepted(response):
            stop_order = response
        else:
            errors["stop_loss"] = {
                "error": "Stop-loss response was not accepted",
                "response": response,
            }
    except Exception as error:
        errors["stop_loss"] = {"error": str(error)}

    try:
        response = place_take_profit_order(
            symbol=symbol,
            side=side,
            take_profit_price=take_profit_price,
            quantity=quantity,
        )
        if _response_is_accepted(response):
            take_profit_order = response
        else:
            errors["take_profit"] = {
                "error": "Take-profit response was not accepted",
                "response": response,
            }
    except Exception as error:
        errors["take_profit"] = {"error": str(error)}

    return {
        "stop_loss_order": stop_order,
        "take_profit_order": take_profit_order,
        "errors": errors,
        "submitted": stop_order is not None and take_profit_order is not None,
    }


def _resize_protection(
    symbol: str,
    side: str,
    remaining_quantity: float,
    stop_price: float,
    take_profit_price: float,
) -> dict:
    """Replace active SL/TP protection with protection for remaining quantity."""
    if side not in {"BUY", "SELL"} or remaining_quantity <= 0:
        return {
            "status": "blocked",
            "protected": False,
            "reason": "Invalid side or remaining quantity for protection resize",
            "side": side,
            "remaining_quantity": remaining_quantity,
        }

    try:
        formatted_quantity = format_quantity(symbol, remaining_quantity)
    except Exception as error:
        return {
            "status": "blocked",
            "protected": False,
            "reason": "Remaining quantity is below Binance minimum/step size",
            "remaining_quantity": remaining_quantity,
            "error": str(error),
        }

    if formatted_quantity <= 0:
        return {
            "status": "blocked",
            "protected": False,
            "reason": "Formatted remaining quantity is zero",
            "remaining_quantity": remaining_quantity,
        }

    try:
        orders = get_open_orders(symbol=symbol)
        if not isinstance(orders, list):
            raise TypeError("Open orders response is not a list")
    except Exception as error:
        return {
            "status": "error",
            "protected": False,
            "reason": "Could not query protection orders",
            "error": str(error),
        }

    close_side = _close_side(side)
    stop_orders, take_profit_orders = _find_protection_orders(orders, close_side)
    resolved_stop = stop_price or _select_stop_price(stop_orders, side)
    resolved_take_profit = take_profit_price or _select_take_profit_price(
        take_profit_orders, side
    )

    if resolved_stop <= 0 or resolved_take_profit <= 0:
        return {
            "status": "unsafe",
            "protected": False,
            "reason": "Active stop-loss and take-profit prices are required",
            "stop_loss_price": resolved_stop,
            "take_profit_price": resolved_take_profit,
        }

    cancellation = _cancel_orders_and_verify(
        symbol=symbol,
        close_side=close_side,
        orders=[*stop_orders, *take_profit_orders],
    )
    if not cancellation.get("verified"):
        return {
            "status": "unsafe",
            "protected": False,
            "reason": "Existing SL/TP orders were not fully cancelled; replacement blocked",
            "remaining_quantity": formatted_quantity,
            "stop_loss_price": resolved_stop,
            "take_profit_price": resolved_take_profit,
            "cancellation": cancellation,
        }

    creation = _create_protection_pair(
        symbol=symbol,
        side=side,
        quantity=formatted_quantity,
        stop_price=resolved_stop,
        take_profit_price=resolved_take_profit,
    )

    protected, verification, attempts = _verify_protection_with_retry(
        symbol=symbol,
        stop_price=resolved_stop,
        take_profit_price=resolved_take_profit,
    )

    return {
        "status": "protected" if protected else "unsafe",
        "protected": protected,
        "remaining_quantity": remaining_quantity,
        "formatted_remaining_quantity": formatted_quantity,
        "stop_loss_price": resolved_stop,
        "take_profit_price": resolved_take_profit,
        "cancellation": cancellation,
        "creation": creation,
        "verification": verification,
        "verification_attempts": attempts,
        "reason": (
            "Protection resized and verified"
            if protected
            else "Remaining position is not fully protected"
        ),
    }


def _normalise_stages(stages: Iterable[dict] | None) -> list[dict]:
    result: list[dict] = []
    seen_names: set[str] = set()

    for index, stage in enumerate(stages or DEFAULT_STAGES, start=1):
        if not isinstance(stage, dict):
            continue
        name = _normalize_text(stage.get("name") or f"TP{index}")
        trigger = max(0.01, _safe_float(stage.get("trigger_percent"), 0.0))
        fraction = max(0.0, _safe_float(stage.get("close_fraction"), 0.0))
        if not name or name in seen_names or fraction <= 0 or fraction >= 1:
            continue
        seen_names.add(name)
        result.append(
            {
                "name": name,
                "trigger_percent": trigger,
                "close_fraction": fraction,
            }
        )

    result.sort(key=lambda item: item["trigger_percent"])
    return result


def _verify_position_reduction(
    symbol: str,
    before_quantity: float,
    expected_close_quantity: float,
    attempts: int = DEFAULT_POSITION_VERIFY_ATTEMPTS,
    delay_seconds: float = DEFAULT_VERIFY_DELAY_SECONDS,
) -> dict:
    last_position = None
    last_error = None
    used_attempts = 0
    tolerance = max(1e-12, expected_close_quantity * 0.05)

    for attempt in range(1, max(1, attempts) + 1):
        used_attempts = attempt
        try:
            last_position = _find_position(symbol)
            remaining = abs(
                _safe_float((last_position or {}).get("positionAmt"), 0.0)
            )
            reduction = before_quantity - remaining
            if remaining < before_quantity and reduction + tolerance >= expected_close_quantity:
                return {
                    "verified": True,
                    "remaining_quantity": remaining,
                    "actual_reduction": reduction,
                    "position": last_position,
                    "attempts": used_attempts,
                    "error": None,
                }
            last_error = None
        except Exception as error:
            last_error = str(error)

        if attempt < attempts:
            time.sleep(max(0.0, delay_seconds))

    remaining = abs(_safe_float((last_position or {}).get("positionAmt"), 0.0))
    return {
        "verified": remaining < before_quantity,
        "remaining_quantity": remaining,
        "actual_reduction": before_quantity - remaining,
        "position": last_position,
        "attempts": used_attempts,
        "error": last_error,
    }


def _position_state_record(
    state: dict,
    key: str,
    symbol: str,
    side: str,
    entry_price: float,
    current_quantity: float,
) -> dict:
    positions_state = state.setdefault("positions", {})
    record = positions_state.setdefault(
        key,
        {
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "original_quantity": current_quantity,
            "completed_stages": [],
            "pending_stage": None,
        },
    )
    record.setdefault("completed_stages", [])
    record.setdefault("pending_stage", None)
    record["original_quantity"] = max(
        current_quantity,
        _safe_float(record.get("original_quantity"), current_quantity),
    )
    return record


def _manage_partial_take_profit_unlocked(
    symbol: str,
    stages: Iterable[dict] | None = None,
    runner_fraction: float = DEFAULT_RUNNER_FRACTION,
    positions: list | None = None,
) -> dict:
    configured_stages = _normalise_stages(stages)
    runner_fraction = min(
        0.95,
        max(0.0, _safe_float(runner_fraction, DEFAULT_RUNNER_FRACTION)),
    )

    if not configured_stages:
        return {
            "status": "blocked",
            "executed": False,
            "symbol": symbol,
            "reason": "No valid TP stages configured",
        }

    total_close_fraction = sum(item["close_fraction"] for item in configured_stages)
    if total_close_fraction > (1.0 - runner_fraction + 1e-9):
        return {
            "status": "blocked",
            "executed": False,
            "symbol": symbol,
            "reason": "Stage close fractions would consume the reserved runner quantity",
            "total_close_fraction": total_close_fraction,
            "runner_fraction": runner_fraction,
        }

    try:
        position = _find_position(symbol, positions)
    except Exception as error:
        return {
            "status": "error",
            "executed": False,
            "symbol": symbol,
            "reason": "Could not query open position",
            "error": str(error),
        }

    if not position:
        return {
            "status": "no_position",
            "executed": False,
            "symbol": symbol,
            "reason": "No open position found",
        }

    amount = _safe_float(position.get("positionAmt"), 0.0)
    current_quantity = abs(amount)
    side = _position_side(amount)
    entry_price = _safe_float(position.get("entryPrice"), 0.0)
    mark_price = _safe_float(position.get("markPrice"), 0.0)

    if side == "NONE" or current_quantity <= 0 or entry_price <= 0 or mark_price <= 0:
        return {
            "status": "blocked",
            "executed": False,
            "symbol": symbol,
            "reason": "Position data is invalid",
            "position_side": side,
            "quantity": current_quantity,
            "entry_price": entry_price,
            "mark_price": mark_price,
        }

    key = _state_key(symbol, side, entry_price)
    with _STATE_LOCK:
        state = _load_state_unlocked()
        position_state = _position_state_record(
            state,
            key,
            symbol,
            side,
            entry_price,
            current_quantity,
        )

        original_quantity = _safe_float(
            position_state.get("original_quantity"), current_quantity
        )
        completed = {
            _normalize_text(name)
            for name in position_state.get("completed_stages", [])
            if _normalize_text(name)
        }
        pending = position_state.get("pending_stage")

        if isinstance(pending, dict) and pending.get("name"):
            pending_name = _normalize_text(pending.get("name"))
            before_quantity = _safe_float(pending.get("before_quantity"), 0.0)
            requested_quantity = _safe_float(pending.get("close_quantity"), 0.0)

            if before_quantity > 0 and current_quantity < before_quantity:
                completed.add(pending_name)
                position_state["completed_stages"] = sorted(completed)
                position_state["pending_stage"] = None
                position_state["last_remaining_quantity"] = current_quantity
                position_state["reconciled_at"] = time.time()
                _save_state_unlocked(state)
            else:
                return {
                    "status": "reconciliation_required",
                    "executed": False,
                    "symbol": symbol,
                    "position_side": side,
                    "current_quantity": current_quantity,
                    "pending_stage": pending,
                    "reason": (
                        "A previously persisted partial-close stage is still pending; "
                        "duplicate execution is blocked"
                    ),
                    "requested_close_quantity": requested_quantity,
                }

        next_stage = None
        stage_trigger_price = 0.0
        for stage in configured_stages:
            if stage["name"] in completed:
                continue
            candidate_trigger = _trigger_price(
                side, entry_price, stage["trigger_percent"]
            )
            if _trigger_reached(side, mark_price, candidate_trigger):
                next_stage = stage
                stage_trigger_price = candidate_trigger
            break  # Stages must complete in order.

        if next_stage is None:
            pending_stage = next(
                (stage for stage in configured_stages if stage["name"] not in completed),
                None,
            )
            if pending_stage is None:
                return {
                    "status": "complete",
                    "executed": False,
                    "symbol": symbol,
                    "position_side": side,
                    "entry_price": entry_price,
                    "mark_price": mark_price,
                    "current_quantity": current_quantity,
                    "original_quantity": original_quantity,
                    "completed_stages": sorted(completed),
                    "runner_active": True,
                    "reason": "All partial take-profit stages are complete",
                }

            return {
                "status": "waiting",
                "executed": False,
                "symbol": symbol,
                "position_side": side,
                "entry_price": entry_price,
                "mark_price": mark_price,
                "current_quantity": current_quantity,
                "original_quantity": original_quantity,
                "next_stage": pending_stage,
                "trigger_price": _trigger_price(
                    side, entry_price, pending_stage["trigger_percent"]
                ),
                "completed_stages": sorted(completed),
                "reason": "Next partial take-profit trigger has not been reached",
            }

        reserved_quantity_raw = original_quantity * runner_fraction
        requested_close_raw = original_quantity * next_stage["close_fraction"]
        maximum_close_raw = max(0.0, current_quantity - reserved_quantity_raw)
        close_raw = min(requested_close_raw, maximum_close_raw)

        try:
            close_quantity = format_quantity(symbol, close_raw)
        except Exception as error:
            return {
                "status": "blocked",
                "executed": False,
                "symbol": symbol,
                "stage": next_stage,
                "reason": "Partial close quantity is below Binance minimum/step size",
                "error": str(error),
                "requested_close_quantity": close_raw,
                "current_quantity": current_quantity,
            }

        if close_quantity <= 0 or close_quantity >= current_quantity:
            return {
                "status": "blocked",
                "executed": False,
                "symbol": symbol,
                "stage": next_stage,
                "reason": "Calculated partial close quantity is unsafe",
                "close_quantity": close_quantity,
                "current_quantity": current_quantity,
                "reserved_runner_quantity": reserved_quantity_raw,
            }

        # Confirm complete exchange-side protection before reducing the position.
        try:
            current_orders = get_open_orders(symbol=symbol)
            if not isinstance(current_orders, list):
                raise TypeError("Open orders response is not a list")
            close_side = _close_side(side)
            stop_orders, take_profit_orders = _find_protection_orders(
                current_orders, close_side
            )
            current_stop_price = _select_stop_price(stop_orders, side)
            current_take_profit_price = _select_take_profit_price(
                take_profit_orders, side
            )
        except Exception as error:
            return {
                "status": "unsafe",
                "executed": False,
                "symbol": symbol,
                "stage": next_stage,
                "reason": "Could not confirm active protection before partial close",
                "error": str(error),
            }

        if current_stop_price <= 0 or current_take_profit_price <= 0:
            return {
                "status": "unsafe",
                "executed": False,
                "symbol": symbol,
                "stage": next_stage,
                "reason": "Partial close blocked because complete SL/TP protection was not found",
                "stop_loss_price": current_stop_price,
                "take_profit_price": current_take_profit_price,
            }

        protected_before, pre_verification, pre_attempts = _verify_protection_with_retry(
            symbol=symbol,
            stop_price=current_stop_price,
            take_profit_price=current_take_profit_price,
            attempts=3,
        )
        if not protected_before:
            return {
                "status": "unsafe",
                "executed": False,
                "symbol": symbol,
                "stage": next_stage,
                "reason": "Existing SL/TP protection could not be verified before partial close",
                "verification": pre_verification,
                "verification_attempts": pre_attempts,
            }

        # Persist intent before order submission. If the process crashes afterwards,
        # the next run blocks duplicate execution and reconciles against quantity.
        pending_record = {
            "name": next_stage["name"],
            "trigger_percent": next_stage["trigger_percent"],
            "close_fraction": next_stage["close_fraction"],
            "before_quantity": current_quantity,
            "close_quantity": close_quantity,
            "created_at": time.time(),
        }
        position_state["pending_stage"] = pending_record
        position_state["last_updated_at"] = time.time()
        try:
            _save_state_unlocked(state)
        except Exception as error:
            position_state["pending_stage"] = None
            return {
                "status": "error",
                "executed": False,
                "symbol": symbol,
                "stage": next_stage,
                "reason": "Could not persist partial-close intent; execution blocked",
                "error": str(error),
            }

    try:
        close_order = close_position(
            symbol=symbol,
            quantity=close_quantity,
            side=side,
        )
    except Exception as error:
        with _STATE_LOCK:
            state = _load_state_unlocked()
            record = state.setdefault("positions", {}).get(key)
            if isinstance(record, dict):
                record["pending_stage"] = None
                record["last_error"] = str(error)
                record["last_updated_at"] = time.time()
                try:
                    _save_state_unlocked(state)
                except Exception:
                    pass
        return {
            "status": "error",
            "executed": False,
            "symbol": symbol,
            "stage": next_stage,
            "reason": "Reduce-only partial close failed",
            "error": str(error),
            "close_quantity": close_quantity,
        }

    if not _response_is_accepted(close_order):
        # Keep pending state fail-closed because an ambiguous API response may still
        # represent an accepted exchange order.
        return {
            "status": "verification_required",
            "executed": False,
            "symbol": symbol,
            "stage": next_stage,
            "reason": "Partial-close response was ambiguous; duplicate retry is blocked",
            "close_order": close_order,
            "pending_stage": pending_record,
        }

    reduction = _verify_position_reduction(
        symbol=symbol,
        before_quantity=current_quantity,
        expected_close_quantity=close_quantity,
    )
    remaining_quantity = _safe_float(reduction.get("remaining_quantity"), 0.0)

    if not reduction.get("verified"):
        return {
            "status": "verification_failed",
            "executed": False,
            "symbol": symbol,
            "stage": next_stage,
            "close_order": close_order,
            "before_quantity": current_quantity,
            "remaining_quantity": remaining_quantity,
            "position_verification": reduction,
            "pending_stage": pending_record,
            "reason": (
                "Partial close was submitted but the exchange reduction could not "
                "be verified; duplicate retry is blocked"
            ),
        }

    protection = None
    if remaining_quantity > 0:
        protection = _resize_protection(
            symbol=symbol,
            side=side,
            remaining_quantity=remaining_quantity,
            stop_price=current_stop_price,
            take_profit_price=current_take_profit_price,
        )

    with _STATE_LOCK:
        state = _load_state_unlocked()
        position_state = _position_state_record(
            state,
            key,
            symbol,
            side,
            entry_price,
            current_quantity,
        )
        completed = {
            _normalize_text(name)
            for name in position_state.get("completed_stages", [])
            if _normalize_text(name)
        }
        completed.add(next_stage["name"])
        position_state["completed_stages"] = sorted(completed)
        position_state["pending_stage"] = None
        position_state["last_remaining_quantity"] = remaining_quantity
        position_state["last_close_order"] = close_order
        position_state["last_updated_at"] = time.time()
        try:
            _save_state_unlocked(state)
            state_saved = True
            state_error = None
        except Exception as error:
            state_saved = False
            state_error = str(error)

    protected = remaining_quantity <= 0 or (protection or {}).get("protected") is True
    status = "executed" if protected and state_saved else "unsafe"
    return {
        "status": status,
        "executed": True,
        "protected": protected,
        "state_saved": state_saved,
        "state_error": state_error,
        "symbol": symbol,
        "position_side": side,
        "stage": next_stage,
        "trigger_price": stage_trigger_price,
        "entry_price": entry_price,
        "mark_price": mark_price,
        "original_quantity": original_quantity,
        "before_quantity": current_quantity,
        "requested_close_quantity": close_quantity,
        "actual_reduction": reduction.get("actual_reduction"),
        "remaining_quantity": remaining_quantity,
        "close_order": close_order,
        "position_verification": reduction,
        "protection": protection,
        "completed_stages": sorted(completed),
        "reason": (
            f"{next_stage['name']} partial take profit executed and remaining position protected"
            if protected and state_saved
            else (
                f"{next_stage['name']} executed, but state persistence failed"
                if not state_saved
                else f"{next_stage['name']} executed but remaining protection is incomplete"
            )
        ),
    }


def manage_partial_take_profit(
    symbol: str,
    stages: Iterable[dict] | None = None,
    runner_fraction: float = DEFAULT_RUNNER_FRACTION,
    positions: list | None = None,
) -> dict:
    """Execute the next eligible partial take-profit stage for one position."""
    normalized_symbol = _normalize_symbol(symbol)
    if not normalized_symbol:
        return {
            "status": "blocked",
            "executed": False,
            "reason": "Symbol is missing",
        }

    lock = _get_symbol_lock(normalized_symbol)
    if not lock.acquire(blocking=False):
        return {
            "status": "locked",
            "executed": False,
            "symbol": normalized_symbol,
            "reason": "Partial take-profit management is already running for this symbol",
        }

    try:
        return _manage_partial_take_profit_unlocked(
            symbol=normalized_symbol,
            stages=stages,
            runner_fraction=runner_fraction,
            positions=positions,
        )
    except Exception as error:
        return {
            "status": "error",
            "executed": False,
            "symbol": normalized_symbol,
            "reason": "Unexpected partial take-profit manager failure",
            "error": str(error),
        }
    finally:
        lock.release()


def manage_partial_take_profit_for_open_positions(
    positions: list | None = None,
    stages: Iterable[dict] | None = None,
    runner_fraction: float = DEFAULT_RUNNER_FRACTION,
) -> list[dict]:
    """Run partial take-profit management for every unique open position."""
    try:
        source = positions if positions is not None else get_open_positions()
        if not isinstance(source, list):
            raise TypeError("Open positions response is not a list")
    except Exception as error:
        return [
            {
                "status": "error",
                "executed": False,
                "reason": "Could not query open positions",
                "error": str(error),
            }
        ]

    results: list[dict] = []
    seen: set[str] = set()
    for position in source:
        if not isinstance(position, dict):
            continue
        symbol = _normalize_symbol(position.get("symbol"))
        amount = _safe_float(position.get("positionAmt"), 0.0)
        if not symbol or amount == 0 or symbol in seen:
            continue
        seen.add(symbol)
        results.append(
            manage_partial_take_profit(
                symbol=symbol,
                stages=stages,
                runner_fraction=runner_fraction,
                positions=source,
            )
        )
    return results