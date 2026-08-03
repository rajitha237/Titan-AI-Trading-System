"""
TitanAI Stop-Loss / Take-Profit Manager v3

Creates and verifies exchange-side protection orders for Binance
USD-M Futures Testnet positions.

Main responsibilities:
- Detect the current open position
- Determine BUY or SELL position direction
- Read SL/TP prices from a Trade Builder plan
- Prevent duplicate protection orders
- Optionally replace existing protection orders
- Create STOP_MARKET and TAKE_PROFIT_MARKET orders
- Verify protection orders through Binance open orders
- Return structured safety status without crashing the trading cycle

Important:
This manager protects existing Binance Testnet positions.
It does not open new entry positions.
"""

from math import isfinite
from typing import Any
import threading
import time

from app.exchange.binance_testnet_client import (
    cancel_open_orders,
    get_open_orders,
    get_open_positions,
    place_stop_loss_order,
    place_take_profit_order,
)


STOP_ORDER_TYPES = {
    "STOP",
    "STOP_MARKET",
}

TAKE_PROFIT_ORDER_TYPES = {
    "TAKE_PROFIT",
    "TAKE_PROFIT_MARKET",
}

ACTIVE_ORDER_STATUSES = {
    "NEW",
    "PARTIALLY_FILLED",
}

PRICE_MATCH_TOLERANCE_PERCENT = 0.05
VERIFICATION_ATTEMPTS = 4
VERIFICATION_DELAY_SECONDS = 0.5

_SYMBOL_LOCKS: dict[str, threading.Lock] = {}
_SYMBOL_LOCKS_GUARD = threading.Lock()


def _get_symbol_lock(symbol: str) -> threading.Lock:
    normalized = _normalize_symbol(symbol)
    with _SYMBOL_LOCKS_GUARD:
        lock = _SYMBOL_LOCKS.get(normalized)
        if lock is None:
            lock = threading.Lock()
            _SYMBOL_LOCKS[normalized] = lock
        return lock


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)

        if not isfinite(result):
            return default

        return result

    except (TypeError, ValueError):
        return default


def _safe_text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    return str(value).strip()


def _safe_bool(
    value: Any,
    default: bool = False,
) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return value != 0

    text = _safe_text(value).lower()
    if text in {"true", "1", "yes", "y"}:
        return True
    if text in {"false", "0", "no", "n", ""}:
        return False
    return default


def _normalize_symbol(
    symbol: str,
) -> str:
    return _safe_text(
        symbol
    ).upper()


def _normalize_side(
    side: str,
) -> str:
    return _safe_text(
        side
    ).upper()


def _normalize_order_type(
    order_type: str,
) -> str:
    return _safe_text(
        order_type
    ).upper()


def _normalize_order_status(
    status: str,
) -> str:
    return _safe_text(
        status
    ).upper()


def _get_position_side(
    position_amount: float,
) -> str:
    if position_amount > 0:
        return "BUY"

    if position_amount < 0:
        return "SELL"

    return "NONE"


def _get_close_side(
    position_side: str,
) -> str:
    if position_side == "BUY":
        return "SELL"

    if position_side == "SELL":
        return "BUY"

    return "NONE"


def _get_stop_price(
    order: dict,
) -> float:
    return _safe_float(
        order.get(
            "stopPrice",
            order.get("price"),
        ),
        0.0,
    )


def _prices_match(
    first_price: float,
    second_price: float,
    tolerance_percent: float = (
        PRICE_MATCH_TOLERANCE_PERCENT
    ),
) -> bool:
    first_price = _safe_float(
        first_price,
        0.0,
    )

    second_price = _safe_float(
        second_price,
        0.0,
    )

    if first_price <= 0 or second_price <= 0:
        return False

    difference_percent = (
        abs(first_price - second_price)
        / second_price
        * 100
    )

    return difference_percent <= tolerance_percent


def _extract_position(
    symbol: str,
    positions: list | None = None,
) -> dict | None:
    symbol = _normalize_symbol(
        symbol
    )

    if positions is None:
        positions = get_open_positions()

    for position in positions or []:
        position_symbol = _normalize_symbol(
            position.get("symbol")
        )

        position_amount = _safe_float(
            position.get("positionAmt"),
            0.0,
        )

        if (
            position_symbol == symbol
            and position_amount != 0
        ):
            return position

    return None


def _classify_open_orders(
    orders: list | None,
) -> dict:
    stop_loss_orders = []
    take_profit_orders = []
    other_orders = []

    for order in orders or []:
        order_type = _normalize_order_type(
            order.get("type")
        )

        order_status = _normalize_order_status(
            order.get("status", "NEW")
        )

        if (
            order_status
            and order_status not in ACTIVE_ORDER_STATUSES
        ):
            continue

        if order_type in STOP_ORDER_TYPES:
            stop_loss_orders.append(order)

        elif order_type in TAKE_PROFIT_ORDER_TYPES:
            take_profit_orders.append(order)

        else:
            other_orders.append(order)

    return {
        "stop_loss_orders": stop_loss_orders,
        "take_profit_orders": take_profit_orders,
        "other_orders": other_orders,
    }


def _find_matching_order(
    orders: list,
    expected_side: str,
    expected_price: float,
) -> dict | None:
    expected_side = _normalize_side(
        expected_side
    )

    for order in orders:
        order_side = _normalize_side(
            order.get("side")
        )

        order_price = _get_stop_price(
            order
        )

        reduce_only = _safe_bool(
            order.get("reduceOnly", False)
        )

        close_position = _safe_bool(
            order.get("closePosition", False)
        )

        closes_position = (
            reduce_only
            or close_position
        )

        if (
            order_side == expected_side
            and closes_position
            and _prices_match(
                order_price,
                expected_price,
            )
        ):
            return order

    return None


def _validate_protection_prices(
    position_side: str,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
) -> list[str]:
    block_reasons = []

    if entry_price <= 0:
        block_reasons.append(
            "Position entry price is invalid"
        )

    if stop_loss_price <= 0:
        block_reasons.append(
            "Stop-loss price is invalid"
        )

    if take_profit_price <= 0:
        block_reasons.append(
            "Take-profit price is invalid"
        )

    if position_side == "BUY":
        if (
            stop_loss_price > 0
            and entry_price > 0
            and stop_loss_price >= entry_price
        ):
            block_reasons.append(
                "BUY stop-loss must be below entry price"
            )

        if (
            take_profit_price > 0
            and entry_price > 0
            and take_profit_price <= entry_price
        ):
            block_reasons.append(
                "BUY take-profit must be above entry price"
            )

    elif position_side == "SELL":
        if (
            stop_loss_price > 0
            and entry_price > 0
            and stop_loss_price <= entry_price
        ):
            block_reasons.append(
                "SELL stop-loss must be above entry price"
            )

        if (
            take_profit_price > 0
            and entry_price > 0
            and take_profit_price >= entry_price
        ):
            block_reasons.append(
                "SELL take-profit must be below entry price"
            )

    else:
        block_reasons.append(
            "Position side is invalid"
        )

    return list(
        dict.fromkeys(block_reasons)
    )


def _build_order_summary(
    order: dict | None,
) -> dict | None:
    if not isinstance(order, dict):
        return None

    return {
        "symbol": order.get("symbol"),
        "order_id": order.get("orderId"),
        "client_order_id": order.get(
            "clientOrderId"
        ),
        "side": order.get("side"),
        "type": order.get("type"),
        "status": order.get("status"),
        "stop_price": _get_stop_price(order),
        "quantity": _safe_float(
            order.get(
                "origQty",
                order.get("quantity"),
            ),
            0.0,
        ),
        "reduce_only": _safe_bool(
            order.get("reduceOnly", False)
        ),
        "close_position": _safe_bool(
            order.get("closePosition", False)
        ),
        "working_type": order.get(
            "workingType"
        ),
    }


def inspect_position_protection(
    symbol: str,
    stop_loss_price: float | None = None,
    take_profit_price: float | None = None,
) -> dict:
    """
    Read-only protection inspection.

    This function does not create or cancel orders.
    """

    symbol = _normalize_symbol(
        symbol
    )

    if not symbol:
        return {
            "status": "blocked",
            "protected": False,
            "symbol": symbol,
            "reason": "Symbol is missing",
        }

    try:
        positions = get_open_positions()
        position = _extract_position(
            symbol=symbol,
            positions=positions,
        )

    except Exception as error:
        return {
            "status": "error",
            "protected": False,
            "symbol": symbol,
            "reason": (
                "Could not query open positions"
            ),
            "error": str(error),
        }

    if not position:
        return {
            "status": "no_position",
            "protected": False,
            "symbol": symbol,
            "reason": (
                "No open position found for symbol"
            ),
        }

    try:
        open_orders = get_open_orders(
            symbol=symbol
        )

    except Exception as error:
        return {
            "status": "error",
            "protected": False,
            "symbol": symbol,
            "position": position,
            "reason": (
                "Could not query open protection orders"
            ),
            "error": str(error),
        }

    classified = _classify_open_orders(
        open_orders
    )

    stop_orders = classified[
        "stop_loss_orders"
    ]

    take_profit_orders = classified[
        "take_profit_orders"
    ]

    position_amount = _safe_float(
        position.get("positionAmt"),
        0.0,
    )

    position_side = _get_position_side(
        position_amount
    )

    close_side = _get_close_side(
        position_side
    )

    expected_stop_price = _safe_float(
        stop_loss_price,
        0.0,
    )

    expected_take_profit_price = _safe_float(
        take_profit_price,
        0.0,
    )

    matching_stop = None
    matching_take_profit = None

    if expected_stop_price > 0:
        matching_stop = _find_matching_order(
            orders=stop_orders,
            expected_side=close_side,
            expected_price=expected_stop_price,
        )

    elif stop_orders:
        matching_stop = stop_orders[0]

    if expected_take_profit_price > 0:
        matching_take_profit = (
            _find_matching_order(
                orders=take_profit_orders,
                expected_side=close_side,
                expected_price=(
                    expected_take_profit_price
                ),
            )
        )

    elif take_profit_orders:
        matching_take_profit = (
            take_profit_orders[0]
        )

    stop_loss_exists = matching_stop is not None
    take_profit_exists = (
        matching_take_profit is not None
    )

    protected = (
        stop_loss_exists
        and take_profit_exists
    )

    if protected:
        reason = (
            "Position has active stop-loss and "
            "take-profit protection"
        )

    elif stop_loss_exists:
        reason = (
            "Stop-loss exists but take-profit "
            "protection is missing"
        )

    elif take_profit_exists:
        reason = (
            "Take-profit exists but stop-loss "
            "protection is missing"
        )

    else:
        reason = (
            "Position does not have verified "
            "SL/TP protection"
        )

    return {
        "status": (
            "protected"
            if protected
            else "incomplete"
        ),
        "protected": protected,
        "symbol": symbol,
        "position_side": position_side,
        "close_side": close_side,
        "position_amount": abs(
            position_amount
        ),
        "entry_price": _safe_float(
            position.get("entryPrice"),
            0.0,
        ),
        "mark_price": _safe_float(
            position.get("markPrice"),
            0.0,
        ),
        "unrealized_profit": _safe_float(
            position.get("unRealizedProfit"),
            0.0,
        ),
        "stop_loss_exists": stop_loss_exists,
        "take_profit_exists": (
            take_profit_exists
        ),
        "stop_loss_order": _build_order_summary(
            matching_stop
        ),
        "take_profit_order": (
            _build_order_summary(
                matching_take_profit
            )
        ),
        "all_stop_loss_orders": [
            _build_order_summary(order)
            for order in stop_orders
        ],
        "all_take_profit_orders": [
            _build_order_summary(order)
            for order in take_profit_orders
        ],
        "reason": reason,
    }


def _protect_open_position_unlocked(
    symbol: str,
    stop_loss_price: float,
    take_profit_price: float,
    replace_existing: bool = False,
) -> dict:
    """
    Create and verify exchange-side SL/TP orders for an open position.

    replace_existing=False:
        Existing matching protection orders are preserved.

    replace_existing=True:
        All existing open orders for the symbol are cancelled before
        new SL/TP protection orders are created.
    """

    symbol = _normalize_symbol(
        symbol
    )

    requested_stop_loss = _safe_float(
        stop_loss_price,
        0.0,
    )

    requested_take_profit = _safe_float(
        take_profit_price,
        0.0,
    )

    warnings = []
    block_reasons = []

    if not symbol:
        block_reasons.append(
            "Symbol is missing"
        )

    if requested_stop_loss <= 0:
        block_reasons.append(
            "Stop-loss price must be greater than zero"
        )

    if requested_take_profit <= 0:
        block_reasons.append(
            "Take-profit price must be greater than zero"
        )

    if block_reasons:
        return {
            "status": "blocked",
            "protected": False,
            "symbol": symbol,
            "stop_loss_price": (
                requested_stop_loss
            ),
            "take_profit_price": (
                requested_take_profit
            ),
            "block_reasons": block_reasons,
            "warnings": warnings,
        }

    try:
        positions = get_open_positions()

        position = _extract_position(
            symbol=symbol,
            positions=positions,
        )

    except Exception as error:
        return {
            "status": "error",
            "protected": False,
            "symbol": symbol,
            "reason": (
                "Could not query the open position"
            ),
            "error": str(error),
            "block_reasons": [],
            "warnings": warnings,
        }

    if not position:
        return {
            "status": "no_position",
            "protected": False,
            "symbol": symbol,
            "reason": (
                "No open position found to protect"
            ),
            "block_reasons": [],
            "warnings": warnings,
        }

    position_amount = _safe_float(
        position.get("positionAmt"),
        0.0,
    )

    quantity = abs(
        position_amount
    )

    position_side = _get_position_side(
        position_amount
    )

    close_side = _get_close_side(
        position_side
    )

    entry_price = _safe_float(
        position.get("entryPrice"),
        0.0,
    )

    mark_price = _safe_float(
        position.get("markPrice"),
        0.0,
    )

    block_reasons.extend(
        _validate_protection_prices(
            position_side=position_side,
            entry_price=entry_price,
            stop_loss_price=(
                requested_stop_loss
            ),
            take_profit_price=(
                requested_take_profit
            ),
        )
    )

    if quantity <= 0:
        block_reasons.append(
            "Position quantity is zero or invalid"
        )

    if block_reasons:
        return {
            "status": "blocked",
            "protected": False,
            "symbol": symbol,
            "position_side": position_side,
            "close_side": close_side,
            "position_amount": quantity,
            "entry_price": entry_price,
            "mark_price": mark_price,
            "stop_loss_price": (
                requested_stop_loss
            ),
            "take_profit_price": (
                requested_take_profit
            ),
            "block_reasons": list(
                dict.fromkeys(block_reasons)
            ),
            "warnings": warnings,
        }

    try:
        existing_orders = get_open_orders(
            symbol=symbol
        )

    except Exception as error:
        return {
            "status": "error",
            "protected": False,
            "symbol": symbol,
            "reason": (
                "Could not query current open orders"
            ),
            "error": str(error),
            "block_reasons": [],
            "warnings": warnings,
        }

    existing_classification = (
        _classify_open_orders(
            existing_orders
        )
    )

    existing_stop_orders = (
        existing_classification[
            "stop_loss_orders"
        ]
    )

    existing_take_profit_orders = (
        existing_classification[
            "take_profit_orders"
        ]
    )

    existing_other_orders = (
        existing_classification[
            "other_orders"
        ]
    )

    if replace_existing and existing_other_orders:
        return {
            "status": "blocked",
            "protected": False,
            "symbol": symbol,
            "reason": (
                "Refusing to cancel unrelated open orders "
                "while replacing protection"
            ),
            "position_side": position_side,
            "position_amount": quantity,
            "entry_price": entry_price,
            "stop_loss_price": requested_stop_loss,
            "take_profit_price": requested_take_profit,
            "other_open_orders": [
                _build_order_summary(order)
                for order in existing_other_orders
            ],
            "block_reasons": [
                "Unrelated open orders exist for symbol"
            ],
            "warnings": warnings,
        }

    matching_stop = _find_matching_order(
        orders=existing_stop_orders,
        expected_side=close_side,
        expected_price=requested_stop_loss,
    )

    matching_take_profit = (
        _find_matching_order(
            orders=existing_take_profit_orders,
            expected_side=close_side,
            expected_price=(
                requested_take_profit
            ),
        )
    )

    cancellation_result = None

    if replace_existing and existing_orders:
        try:
            cancellation_result = (
                cancel_open_orders(
                    symbol=symbol
                )
            )

            remaining_orders = get_open_orders(symbol=symbol)
            remaining_classification = _classify_open_orders(remaining_orders)
            remaining_protection = (
                remaining_classification["stop_loss_orders"]
                + remaining_classification["take_profit_orders"]
            )
            if remaining_protection:
                return {
                    "status": "error",
                    "protected": False,
                    "symbol": symbol,
                    "reason": "Existing protection orders were not fully cancelled",
                    "position_side": position_side,
                    "position_amount": quantity,
                    "entry_price": entry_price,
                    "stop_loss_price": requested_stop_loss,
                    "take_profit_price": requested_take_profit,
                    "remaining_orders": [
                        _build_order_summary(order)
                        for order in remaining_protection
                    ],
                    "block_reasons": [],
                    "warnings": warnings,
                }

            existing_orders = []
            existing_stop_orders = []
            existing_take_profit_orders = []
            matching_stop = None
            matching_take_profit = None

        except Exception as error:
            return {
                "status": "error",
                "protected": False,
                "symbol": symbol,
                "reason": (
                    "Could not cancel existing orders"
                ),
                "error": str(error),
                "position_side": position_side,
                "position_amount": quantity,
                "entry_price": entry_price,
                "stop_loss_price": (
                    requested_stop_loss
                ),
                "take_profit_price": (
                    requested_take_profit
                ),
                "block_reasons": [],
                "warnings": warnings,
            }

    stop_loss_created = False
    take_profit_created = False

    stop_loss_response = matching_stop
    take_profit_response = (
        matching_take_profit
    )

    stop_loss_error = None
    take_profit_error = None

    if matching_stop is None:
        try:
            stop_loss_response = (
                place_stop_loss_order(
                    symbol=symbol,
                    side=position_side,
                    stop_price=(
                        requested_stop_loss
                    ),
                    quantity=quantity,
                )
            )

            stop_loss_created = True

        except Exception as error:
            stop_loss_error = str(error)

    else:
        warnings.append(
            "Matching stop-loss order already exists"
        )

    if matching_take_profit is None:
        try:
            take_profit_response = (
                place_take_profit_order(
                    symbol=symbol,
                    side=position_side,
                    take_profit_price=(
                        requested_take_profit
                    ),
                    quantity=quantity,
                )
            )

            take_profit_created = True

        except Exception as error:
            take_profit_error = str(error)

    else:
        warnings.append(
            "Matching take-profit order already exists"
        )

    verification = {
        "status": "error",
        "protected": False,
        "reason": "Protection verification did not run",
    }
    verification_attempts = 0

    for attempt in range(1, VERIFICATION_ATTEMPTS + 1):
        verification_attempts = attempt
        try:
            verification = inspect_position_protection(
                symbol=symbol,
                stop_loss_price=requested_stop_loss,
                take_profit_price=requested_take_profit,
            )
        except Exception as error:
            verification = {
                "status": "error",
                "protected": False,
                "reason": "Protection verification failed",
                "error": str(error),
            }

        if bool(verification.get("protected", False)):
            break

        if attempt < VERIFICATION_ATTEMPTS:
            time.sleep(VERIFICATION_DELAY_SECONDS)

    protected = bool(
        verification.get(
            "protected",
            False,
        )
    )

    creation_errors = {}

    if stop_loss_error:
        creation_errors[
            "stop_loss"
        ] = stop_loss_error

    if take_profit_error:
        creation_errors[
            "take_profit"
        ] = take_profit_error

    if protected:
        status = "protected"
        reason = (
            "Stop-loss and take-profit protection "
            "are active and verified"
        )

    elif stop_loss_error or take_profit_error:
        status = "partial_failure"
        reason = (
            "One or more protection orders could "
            "not be created or verified"
        )

    else:
        status = "verification_failed"
        reason = (
            "Protection orders were submitted but "
            "complete protection was not verified"
        )

    return {
        "status": status,
        "protected": protected,
        "symbol": symbol,

        "position_side": position_side,
        "close_side": close_side,
        "position_amount": quantity,
        "entry_price": entry_price,
        "mark_price": mark_price,

        "stop_loss_price": (
            requested_stop_loss
        ),
        "take_profit_price": (
            requested_take_profit
        ),

        "replace_existing": (
            replace_existing
        ),
        "cancellation_result": (
            cancellation_result
        ),

        "stop_loss_created": (
            stop_loss_created
        ),
        "take_profit_created": (
            take_profit_created
        ),

        "stop_loss_response": (
            stop_loss_response
        ),
        "take_profit_response": (
            take_profit_response
        ),

        "stop_loss_order": (
            _build_order_summary(
                stop_loss_response
            )
        ),
        "take_profit_order": (
            _build_order_summary(
                take_profit_response
            )
        ),

        "creation_errors": creation_errors,
        "verification": verification,
        "verification_attempts": verification_attempts,

        "reason": reason,
        "block_reasons": [],
        "warnings": list(
            dict.fromkeys(warnings)
        ),
    }


def protect_open_position(
    symbol: str,
    stop_loss_price: float,
    take_profit_price: float,
    replace_existing: bool = False,
) -> dict:
    """Thread-safe public protection entry point."""
    normalized_symbol = _normalize_symbol(symbol)
    lock = _get_symbol_lock(normalized_symbol)

    if not lock.acquire(blocking=False):
        return {
            "status": "blocked",
            "protected": False,
            "symbol": normalized_symbol,
            "reason": "Protection update is already running for symbol",
            "block_reasons": [
                "Concurrent protection update prevented"
            ],
            "warnings": [],
        }

    try:
        return _protect_open_position_unlocked(
            symbol=normalized_symbol,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            replace_existing=replace_existing,
        )
    finally:
        lock.release()


def protect_verified_execution(
    execution: dict | None,
    trade_plan: dict | None,
    replace_existing: bool = False,
) -> dict:
    """
    Protect an entry only after the Testnet Executor verifies that the
    entry order was filled.

    Expected execution status:
    - verified_filled

    Expected trade_plan fields:
    - symbol
    - stop_loss_price
    - take_profit_price
    """

    execution = execution or {}
    trade_plan = trade_plan or {}

    execution_status = _safe_text(
        execution.get("status")
    ).lower()

    verification = execution.get(
        "verification",
        {},
    ) or {}

    filled = bool(
        verification.get(
            "filled",
            False,
        )
    )

    execution_success = bool(
        verification.get(
            "execution_success",
            False,
        )
    )

    blocked_statuses = {
        "blocked",
        "error",
        "failed",
        "skipped",
        "rejected",
    }

    if not (
        execution_status not in blocked_statuses
        and filled
        and execution_success
    ):
        return {
            "status": "blocked",
            "protected": False,
            "reason": (
                "Entry order is not verified as fully filled"
            ),
            "execution_status": (
                execution_status
            ),
            "verification_status": (
                verification.get("status")
            ),
            "block_reasons": [
                "Verified filled entry is required"
            ],
        }

    symbol = _normalize_symbol(
        trade_plan.get(
            "symbol",
            execution.get("symbol"),
        )
    )

    stop_loss_price = _safe_float(
        trade_plan.get(
            "stop_loss_price"
        ),
        0.0,
    )

    take_profit_price = _safe_float(
        trade_plan.get(
            "take_profit_price"
        ),
        0.0,
    )

    return protect_open_position(
        symbol=symbol,
        stop_loss_price=stop_loss_price,
        take_profit_price=(
            take_profit_price
        ),
        replace_existing=(
            replace_existing
        ),
    )