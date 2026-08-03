"""
TitanAI Trailing Stop Manager v2

Safely advances an existing exchange-side stop loss as an open Binance USD-M
Futures Testnet position becomes profitable. The active take-profit order is
preserved.

Safety properties:
- Supports BUY and SELL positions
- Activates only after a configurable profit threshold
- Uses a per-symbol lock to prevent concurrent stop replacement
- Never moves a stop backwards
- Requires and preserves active exchange-side SL/TP protection
- Cancels only the selected active stop-loss algo order
- Confirms cancellation before submitting the replacement
- Validates exchange responses without trusting truthy strings
- Restores and verifies the previous stop if replacement fails
- Retries final SL/TP verification for exchange propagation delays
- Returns structured fail-closed results without crashing the scheduler
"""

from __future__ import annotations

import threading
import time
from math import isfinite
from typing import Any

from app.exchange.binance_testnet_client import (
    cancel_algo_order,
    format_price,
    get_open_orders,
    get_open_positions,
    place_stop_loss_order,
)
from app.trader.sl_tp_manager import inspect_position_protection

DEFAULT_ACTIVATION_PERCENT = 0.75
DEFAULT_TRAILING_DISTANCE_PERCENT = 0.30
DEFAULT_MINIMUM_MOVE_PERCENT = 0.10
DEFAULT_CANCEL_VERIFY_ATTEMPTS = 4
DEFAULT_PROTECTION_VERIFY_ATTEMPTS = 5
DEFAULT_VERIFY_DELAY_SECONDS = 0.35

STOP_ORDER_TYPES = {"STOP", "STOP_MARKET"}
TAKE_PROFIT_ORDER_TYPES = {"TAKE_PROFIT", "TAKE_PROFIT_MARKET"}
ACTIVE_ORDER_STATUSES = {"NEW", "PARTIALLY_FILLED"}
TERMINAL_CANCEL_STATUSES = {
    "CANCELED",
    "CANCELLED",
    "EXPIRED",
    "REJECTED",
    "FILLED",
}

_LOCKS_GUARD = threading.Lock()
_SYMBOL_LOCKS: dict[str, threading.Lock] = {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
        return result if isfinite(result) else default
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


def _position_side(position_amount: float) -> str:
    if position_amount > 0:
        return "BUY"
    if position_amount < 0:
        return "SELL"
    return "NONE"


def _close_side(position_side: str) -> str:
    if position_side == "BUY":
        return "SELL"
    if position_side == "SELL":
        return "BUY"
    return "NONE"


def _stop_price(order: dict | None) -> float:
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


def _find_position(symbol: str, positions: list | None = None) -> dict | None:
    source = positions if positions is not None else get_open_positions(symbol=symbol)
    if not isinstance(source, list):
        raise TypeError("Open positions response is not a list")

    for position in source:
        if not isinstance(position, dict):
            continue
        amount = _safe_float(position.get("positionAmt"), 0.0)
        if _normalize_symbol(position.get("symbol")) == symbol and amount != 0:
            return position
    return None


def _active_close_orders(
    orders: list,
    order_types: set[str],
    close_side: str,
) -> list[dict]:
    matches: list[dict] = []
    for order in orders or []:
        if not isinstance(order, dict):
            continue
        if (
            _normalize_text(order.get("type")) in order_types
            and _normalize_text(order.get("status", "NEW")) in ACTIVE_ORDER_STATUSES
            and _normalize_text(order.get("side")) == close_side
            and _order_closes_position(order)
        ):
            matches.append(order)
    return matches


def _find_active_stop(
    orders: list,
    close_side: str,
    position_side: str,
) -> dict | None:
    candidates = _active_close_orders(orders, STOP_ORDER_TYPES, close_side)
    if not candidates:
        return None

    # If duplicates already exist, choose the most protective stop.
    candidates.sort(key=_stop_price, reverse=(position_side == "BUY"))
    return candidates[0]


def _find_active_take_profit_price(orders: list, close_side: str) -> float:
    candidates = _active_close_orders(orders, TAKE_PROFIT_ORDER_TYPES, close_side)
    prices = [_stop_price(order) for order in candidates]
    prices = [price for price in prices if price > 0]
    return prices[0] if prices else 0.0


def _activation_price(
    side: str,
    entry_price: float,
    activation_percent: float,
) -> float:
    factor = activation_percent / 100.0
    return (
        entry_price * (1.0 + factor)
        if side == "BUY"
        else entry_price * (1.0 - factor)
    )


def _trailing_stop_price(
    side: str,
    mark_price: float,
    trailing_distance_percent: float,
) -> float:
    factor = trailing_distance_percent / 100.0
    return (
        mark_price * (1.0 - factor)
        if side == "BUY"
        else mark_price * (1.0 + factor)
    )


def _activation_reached(side: str, mark_price: float, activation_price: float) -> bool:
    return (
        mark_price >= activation_price
        if side == "BUY"
        else mark_price <= activation_price
    )


def _is_improved_stop(side: str, current_stop: float, target_stop: float) -> bool:
    if current_stop <= 0:
        return False
    return target_stop > current_stop if side == "BUY" else target_stop < current_stop


def _minimum_move_reached(
    side: str,
    current_stop: float,
    target_stop: float,
    entry_price: float,
    minimum_move_percent: float,
) -> bool:
    required_move = entry_price * (minimum_move_percent / 100.0)
    return (
        (target_stop - current_stop) >= required_move
        if side == "BUY"
        else (current_stop - target_stop) >= required_move
    )


def _stop_is_valid_against_mark(side: str, stop_price: float, mark_price: float) -> bool:
    if side == "BUY":
        return 0 < stop_price < mark_price
    return stop_price > mark_price > 0


def _validate_new_stop_response(response: Any) -> tuple[bool, str | None]:
    if not isinstance(response, dict):
        return False, "Stop-order response is not a dictionary"

    order_id = _order_id(response)
    client_order_id = response.get("clientOrderId", response.get("clientAlgoId"))
    status = _normalize_text(response.get("status"))

    if order_id is None and not client_order_id:
        return False, "Stop-order response has no exchange order identifier"
    if status in {"REJECTED", "EXPIRED", "CANCELED", "CANCELLED"}:
        return False, f"Stop-order response has terminal status {status}"
    return True, None


def _order_still_active(symbol: str, old_order_id: int | str) -> bool:
    orders = get_open_orders(symbol=symbol)
    if not isinstance(orders, list):
        raise TypeError("Open orders response is not a list")

    expected = str(old_order_id)
    for order in orders:
        if not isinstance(order, dict):
            continue
        if str(_order_id(order)) != expected:
            continue
        status = _normalize_text(order.get("status", "NEW"))
        return status not in TERMINAL_CANCEL_STATUSES
    return False


def _confirm_cancellation(
    symbol: str,
    old_order_id: int | str,
    attempts: int,
    delay_seconds: float,
) -> dict:
    last_error = None
    total_attempts = max(1, attempts)

    for attempt in range(1, total_attempts + 1):
        try:
            if not _order_still_active(symbol, old_order_id):
                return {"confirmed": True, "attempts": attempt, "error": None}
        except Exception as error:
            last_error = str(error)

        if attempt < total_attempts:
            time.sleep(max(0.0, delay_seconds))

    return {
        "confirmed": False,
        "attempts": total_attempts,
        "error": last_error,
    }


def _verify_protection_with_retry(
    symbol: str,
    stop_loss_price: float,
    take_profit_price: float,
    attempts: int,
    delay_seconds: float,
) -> dict:
    last_result: dict = {
        "status": "error",
        "protected": False,
        "reason": "Protection verification did not run",
    }
    total_attempts = max(1, attempts)

    for attempt in range(1, total_attempts + 1):
        try:
            result = inspect_position_protection(
                symbol=symbol,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price or None,
            )
            last_result = result if isinstance(result, dict) else {
                "status": "error",
                "protected": False,
                "reason": "Protection inspection returned an invalid response",
            }
        except Exception as error:
            last_result = {
                "status": "error",
                "protected": False,
                "reason": "Protection verification failed",
                "error": str(error),
            }

        last_result = dict(last_result)
        last_result["verification_attempts"] = attempt
        if last_result.get("protected") is True:
            return last_result
        if attempt < total_attempts:
            time.sleep(max(0.0, delay_seconds))

    return last_result


def _restore_previous_stop(
    symbol: str,
    side: str,
    quantity: float,
    old_stop_price: float,
    take_profit_price: float,
    verification_attempts: int,
    delay_seconds: float,
) -> dict:
    try:
        response = place_stop_loss_order(
            symbol=symbol,
            side=side,
            stop_price=old_stop_price,
            quantity=quantity,
        )
    except Exception as error:
        return {
            "restored": False,
            "response": None,
            "verification": None,
            "error": str(error),
        }

    valid, validation_error = _validate_new_stop_response(response)
    verification = _verify_protection_with_retry(
        symbol=symbol,
        stop_loss_price=old_stop_price,
        take_profit_price=take_profit_price,
        attempts=verification_attempts,
        delay_seconds=delay_seconds,
    )
    restored = valid and verification.get("protected") is True
    return {
        "restored": restored,
        "response": response,
        "verification": verification,
        "error": validation_error,
    }


def _manage_trailing_stop_locked(
    symbol: str,
    activation_percent: float,
    trailing_distance_percent: float,
    minimum_move_percent: float,
    positions: list | None,
    cancel_verify_attempts: int,
    protection_verify_attempts: int,
    verify_delay_seconds: float,
) -> dict:
    try:
        position = _find_position(symbol=symbol, positions=positions)
    except Exception as error:
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Could not query open position",
            "error": str(error),
        }

    if not position:
        return {
            "status": "no_position",
            "moved": False,
            "symbol": symbol,
            "reason": "No open position found",
        }

    amount = _safe_float(position.get("positionAmt"), 0.0)
    quantity = abs(amount)
    side = _position_side(amount)
    close_side = _close_side(side)
    entry_price = _safe_float(position.get("entryPrice"), 0.0)
    mark_price = _safe_float(position.get("markPrice"), 0.0)

    if (
        side == "NONE"
        or close_side == "NONE"
        or quantity <= 0
        or entry_price <= 0
        or mark_price <= 0
    ):
        return {
            "status": "blocked",
            "moved": False,
            "symbol": symbol,
            "reason": "Position data is invalid",
            "position_side": side,
            "quantity": quantity,
            "entry_price": entry_price,
            "mark_price": mark_price,
        }

    try:
        activation_price = _safe_float(
            format_price(
                symbol,
                _activation_price(side, entry_price, activation_percent),
            ),
            0.0,
        )
        target_stop = _safe_float(
            format_price(
                symbol,
                _trailing_stop_price(side, mark_price, trailing_distance_percent),
            ),
            0.0,
        )
    except Exception as error:
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Could not format trailing-stop prices",
            "error": str(error),
        }

    if activation_price <= 0 or target_stop <= 0:
        return {
            "status": "blocked",
            "moved": False,
            "symbol": symbol,
            "reason": "Formatted activation or trailing-stop price is invalid",
            "activation_price": activation_price,
            "target_stop_price": target_stop,
        }

    if not _activation_reached(side, mark_price, activation_price):
        return {
            "status": "waiting",
            "moved": False,
            "symbol": symbol,
            "position_side": side,
            "entry_price": entry_price,
            "mark_price": mark_price,
            "activation_price": activation_price,
            "activation_percent": activation_percent,
            "trailing_distance_percent": trailing_distance_percent,
            "reason": "Trailing-stop activation threshold has not been reached",
        }

    if not _stop_is_valid_against_mark(side, target_stop, mark_price):
        return {
            "status": "blocked",
            "moved": False,
            "symbol": symbol,
            "position_side": side,
            "entry_price": entry_price,
            "mark_price": mark_price,
            "target_stop_price": target_stop,
            "reason": "Calculated trailing stop is invalid relative to the current mark price",
        }

    try:
        orders = get_open_orders(symbol=symbol)
        if not isinstance(orders, list):
            raise TypeError("Open orders response is not a list")
    except Exception as error:
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Could not query open orders",
            "error": str(error),
        }

    current_stop_order = _find_active_stop(orders, close_side, side)
    current_stop = _stop_price(current_stop_order)
    take_profit_price = _find_active_take_profit_price(orders, close_side)

    if current_stop_order is None or current_stop <= 0:
        return {
            "status": "unsafe",
            "moved": False,
            "protected": False,
            "symbol": symbol,
            "reason": "No valid active stop-loss order exists; trailing replacement was not attempted",
            "take_profit_price": take_profit_price,
        }

    if take_profit_price <= 0:
        return {
            "status": "unsafe",
            "moved": False,
            "protected": False,
            "symbol": symbol,
            "reason": "No active take-profit order exists; trailing replacement was not attempted",
            "current_stop_price": current_stop,
        }

    if not _is_improved_stop(side, current_stop, target_stop):
        verification = _verify_protection_with_retry(
            symbol=symbol,
            stop_loss_price=current_stop,
            take_profit_price=take_profit_price,
            attempts=protection_verify_attempts,
            delay_seconds=verify_delay_seconds,
        )
        protected = verification.get("protected") is True
        return {
            "status": "already_protected" if protected else "unsafe",
            "moved": False,
            "protected": protected,
            "symbol": symbol,
            "position_side": side,
            "entry_price": entry_price,
            "mark_price": mark_price,
            "activation_price": activation_price,
            "current_stop_price": current_stop,
            "target_stop_price": target_stop,
            "take_profit_price": take_profit_price,
            "verification": verification,
            "reason": (
                "Existing stop is already at the calculated trailing level or better"
                if protected
                else "Existing stop is at or beyond the target, but complete SL/TP protection was not verified"
            ),
        }

    if not _minimum_move_reached(
        side,
        current_stop,
        target_stop,
        entry_price,
        minimum_move_percent,
    ):
        return {
            "status": "waiting_for_step",
            "moved": False,
            "symbol": symbol,
            "position_side": side,
            "entry_price": entry_price,
            "mark_price": mark_price,
            "activation_price": activation_price,
            "current_stop_price": current_stop,
            "target_stop_price": target_stop,
            "minimum_move_percent": minimum_move_percent,
            "reason": "Calculated stop improvement is smaller than the minimum move threshold",
        }

    old_order_id = _order_id(current_stop_order)
    if old_order_id is None:
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Existing stop-loss order has no cancellable order ID",
        }

    try:
        cancellation = cancel_algo_order(symbol=symbol, order_id=old_order_id)
    except Exception as error:
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Could not cancel existing stop loss",
            "error": str(error),
            "old_stop_price": current_stop,
        }

    cancellation_confirmation = _confirm_cancellation(
        symbol=symbol,
        old_order_id=old_order_id,
        attempts=cancel_verify_attempts,
        delay_seconds=verify_delay_seconds,
    )
    if cancellation_confirmation.get("confirmed") is not True:
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Existing stop-loss cancellation was not confirmed; replacement was not submitted",
            "old_stop_price": current_stop,
            "cancellation": cancellation,
            "cancellation_confirmation": cancellation_confirmation,
        }

    try:
        new_stop_order = place_stop_loss_order(
            symbol=symbol,
            side=side,
            stop_price=target_stop,
            quantity=quantity,
        )
        response_valid, response_error = _validate_new_stop_response(new_stop_order)
        if not response_valid:
            raise RuntimeError(response_error or "Replacement stop response is invalid")
    except Exception as replacement_error:
        restore = _restore_previous_stop(
            symbol=symbol,
            side=side,
            quantity=quantity,
            old_stop_price=current_stop,
            take_profit_price=take_profit_price,
            verification_attempts=protection_verify_attempts,
            delay_seconds=verify_delay_seconds,
        )
        return {
            "status": "restored" if restore.get("restored") else "critical",
            "moved": False,
            "protected": restore.get("restored") is True,
            "symbol": symbol,
            "reason": "Trailing stop creation failed; previous stop restoration attempted",
            "replacement_error": str(replacement_error),
            "restore": restore,
            "cancellation": cancellation,
            "cancellation_confirmation": cancellation_confirmation,
        }

    verification = _verify_protection_with_retry(
        symbol=symbol,
        stop_loss_price=target_stop,
        take_profit_price=take_profit_price,
        attempts=protection_verify_attempts,
        delay_seconds=verify_delay_seconds,
    )
    protected = verification.get("protected") is True

    return {
        "status": "moved" if protected else "unsafe",
        "moved": protected,
        "protected": protected,
        "symbol": symbol,
        "position_side": side,
        "close_side": close_side,
        "quantity": quantity,
        "entry_price": entry_price,
        "mark_price": mark_price,
        "activation_price": activation_price,
        "activation_percent": activation_percent,
        "trailing_distance_percent": trailing_distance_percent,
        "minimum_move_percent": minimum_move_percent,
        "old_stop_price": current_stop,
        "new_stop_price": target_stop,
        "take_profit_price": take_profit_price,
        "cancellation": cancellation,
        "cancellation_confirmation": cancellation_confirmation,
        "new_stop_order": new_stop_order,
        "verification": verification,
        "reason": (
            "Trailing stop advanced and verified"
            if protected
            else "New trailing stop was submitted but complete SL/TP protection was not verified"
        ),
    }


def manage_trailing_stop(
    symbol: str,
    activation_percent: float = DEFAULT_ACTIVATION_PERCENT,
    trailing_distance_percent: float = DEFAULT_TRAILING_DISTANCE_PERCENT,
    minimum_move_percent: float = DEFAULT_MINIMUM_MOVE_PERCENT,
    positions: list | None = None,
    cancel_verify_attempts: int = DEFAULT_CANCEL_VERIFY_ATTEMPTS,
    protection_verify_attempts: int = DEFAULT_PROTECTION_VERIFY_ATTEMPTS,
    verify_delay_seconds: float = DEFAULT_VERIFY_DELAY_SECONDS,
) -> dict:
    """Advance one position's stop loss when trailing conditions are met."""

    symbol = _normalize_symbol(symbol)
    activation_percent = max(
        0.01,
        _safe_float(activation_percent, DEFAULT_ACTIVATION_PERCENT),
    )
    trailing_distance_percent = max(
        0.01,
        _safe_float(
            trailing_distance_percent,
            DEFAULT_TRAILING_DISTANCE_PERCENT,
        ),
    )
    minimum_move_percent = max(
        0.0,
        _safe_float(minimum_move_percent, DEFAULT_MINIMUM_MOVE_PERCENT),
    )
    cancel_verify_attempts = max(
        1,
        int(_safe_float(cancel_verify_attempts, DEFAULT_CANCEL_VERIFY_ATTEMPTS)),
    )
    protection_verify_attempts = max(
        1,
        int(
            _safe_float(
                protection_verify_attempts,
                DEFAULT_PROTECTION_VERIFY_ATTEMPTS,
            )
        ),
    )
    verify_delay_seconds = max(
        0.0,
        _safe_float(verify_delay_seconds, DEFAULT_VERIFY_DELAY_SECONDS),
    )

    if not symbol:
        return {"status": "blocked", "moved": False, "reason": "Symbol is missing"}

    if trailing_distance_percent >= activation_percent:
        return {
            "status": "blocked",
            "moved": False,
            "symbol": symbol,
            "reason": "Trailing distance must be smaller than the activation threshold",
            "activation_percent": activation_percent,
            "trailing_distance_percent": trailing_distance_percent,
        }

    if positions is not None and not isinstance(positions, list):
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Provided positions response is not a list",
        }

    lock = _get_symbol_lock(symbol)
    if not lock.acquire(blocking=False):
        return {
            "status": "skipped",
            "moved": False,
            "symbol": symbol,
            "reason": "A trailing-stop operation is already running for this symbol",
        }

    try:
        return _manage_trailing_stop_locked(
            symbol=symbol,
            activation_percent=activation_percent,
            trailing_distance_percent=trailing_distance_percent,
            minimum_move_percent=minimum_move_percent,
            positions=positions,
            cancel_verify_attempts=cancel_verify_attempts,
            protection_verify_attempts=protection_verify_attempts,
            verify_delay_seconds=verify_delay_seconds,
        )
    except Exception as error:
        return {
            "status": "error",
            "moved": False,
            "symbol": symbol,
            "reason": "Unexpected trailing-stop manager failure",
            "error": str(error),
        }
    finally:
        lock.release()


def manage_trailing_stop_for_open_positions(
    positions: list | None = None,
    activation_percent: float = DEFAULT_ACTIVATION_PERCENT,
    trailing_distance_percent: float = DEFAULT_TRAILING_DISTANCE_PERCENT,
    minimum_move_percent: float = DEFAULT_MINIMUM_MOVE_PERCENT,
) -> list[dict]:
    """Run trailing-stop management once for every unique open position."""

    if positions is None:
        try:
            positions = get_open_positions()
        except Exception as error:
            return [{
                "status": "error",
                "moved": False,
                "reason": "Could not query open positions",
                "error": str(error),
            }]

    if not isinstance(positions, list):
        return [{
            "status": "error",
            "moved": False,
            "reason": "Open positions response is not a list",
        }]

    results: list[dict] = []
    seen: set[str] = set()

    for position in positions:
        if not isinstance(position, dict):
            continue

        symbol = _normalize_symbol(position.get("symbol"))
        amount = _safe_float(position.get("positionAmt"), 0.0)
        if not symbol or amount == 0 or symbol in seen:
            continue

        seen.add(symbol)
        results.append(
            manage_trailing_stop(
                symbol=symbol,
                activation_percent=activation_percent,
                trailing_distance_percent=trailing_distance_percent,
                minimum_move_percent=minimum_move_percent,
                positions=positions,
            )
        )

    return results