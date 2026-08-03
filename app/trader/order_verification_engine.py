"""
TitanAI Order Verification Engine v1

Verifies Binance Futures orders after submission.

Features:
- Validates the initial order response
- Queries Binance by order ID or client order ID
- Detects FILLED, PARTIALLY_FILLED, NEW, CANCELED,
  EXPIRED and REJECTED states
- Calculates filled and remaining quantity
- Calculates average execution price
- Uses retry with exponential backoff
- Distinguishes retryable and terminal order states
- Protects against missing or invalid order data
"""

import time
from math import isfinite
from typing import Any

from app.exchange.binance_testnet_client import client


FINAL_SUCCESS_STATUSES = {
    "FILLED",
}

FINAL_FAILURE_STATUSES = {
    "CANCELED",
    "EXPIRED",
    "EXPIRED_IN_MATCH",
    "REJECTED",
}

PENDING_STATUSES = {
    "NEW",
    "PARTIALLY_FILLED",
    "PENDING_NEW",
}

KNOWN_STATUSES = (
    FINAL_SUCCESS_STATUSES
    | FINAL_FAILURE_STATUSES
    | PENDING_STATUSES
)


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


def _safe_int(
    value: Any,
    default: int | None = None,
) -> int | None:
    try:
        return int(value)

    except (TypeError, ValueError):
        return default


def _safe_text(
    value: Any,
    default: str = "",
) -> str:
    if value is None:
        return default

    return str(value).strip()


def _normalize_status(
    status: Any,
) -> str:
    normalized = _safe_text(
        status,
        "UNKNOWN",
    ).upper()

    return normalized or "UNKNOWN"


def _extract_order_id(
    order_response: dict | None,
) -> int | None:
    order_response = order_response or {}

    return _safe_int(
        order_response.get("orderId")
    )


def _extract_client_order_id(
    order_response: dict | None,
) -> str | None:
    order_response = order_response or {}

    client_order_id = (
        order_response.get("clientOrderId")
        or order_response.get("origClientOrderId")
    )

    client_order_id = _safe_text(
        client_order_id
    )

    return client_order_id or None


def _calculate_average_price(
    order: dict,
    executed_quantity: float,
) -> float:
    average_price = _safe_float(
        order.get("avgPrice"),
        0.0,
    )

    if average_price > 0:
        return average_price

    cumulative_quote = _safe_float(
        order.get("cumQuote"),
        0.0,
    )

    if cumulative_quote > 0 and executed_quantity > 0:
        return cumulative_quote / executed_quantity

    price = _safe_float(
        order.get("price"),
        0.0,
    )

    return price


def _is_retryable_exception(
    error: Exception,
) -> bool:
    message = str(error).lower()

    retryable_messages = [
        "timeout",
        "timed out",
        "connection",
        "temporarily unavailable",
        "service unavailable",
        "gateway",
        "too many requests",
        "rate limit",
        "internal error",
        "network",
        "remote disconnected",
    ]

    return any(
        phrase in message
        for phrase in retryable_messages
    )


def _build_verification_result(
    order: dict,
    attempts: int,
    source: str,
    query_error: str | None = None,
) -> dict:
    status = _normalize_status(
        order.get("status")
    )

    original_quantity = _safe_float(
        order.get(
            "origQty",
            order.get("quantity"),
        ),
        0.0,
    )

    executed_quantity = _safe_float(
        order.get(
            "executedQty",
            order.get("cumQty"),
        ),
        0.0,
    )

    remaining_quantity = max(
        0.0,
        original_quantity - executed_quantity,
    )

    average_price = _calculate_average_price(
        order=order,
        executed_quantity=executed_quantity,
    )

    order_id = _safe_int(
        order.get("orderId")
    )

    client_order_id = _safe_text(
        order.get(
            "clientOrderId",
            order.get("origClientOrderId"),
        )
    )

    symbol = _safe_text(
        order.get("symbol")
    ).upper()

    side = _safe_text(
        order.get("side")
    ).upper()

    order_type = _safe_text(
        order.get("type")
    ).upper()

    reduce_only = bool(
        order.get("reduceOnly", False)
    )

    verified = status in KNOWN_STATUSES
    filled = status == "FILLED"
    partially_filled = (
        status == "PARTIALLY_FILLED"
        or (
            executed_quantity > 0
            and remaining_quantity > 0
        )
    )

    terminal = (
        status in FINAL_SUCCESS_STATUSES
        or status in FINAL_FAILURE_STATUSES
    )

    retry_required = (
        status in PENDING_STATUSES
        or status == "UNKNOWN"
    )

    execution_success = filled

    if filled:
        reason = "Order filled successfully"

    elif partially_filled:
        reason = (
            "Order is partially filled and still requires monitoring"
        )

    elif status == "NEW":
        reason = (
            "Order is accepted but has not filled yet"
        )

    elif status in FINAL_FAILURE_STATUSES:
        reason = (
            f"Order reached terminal failure state: {status}"
        )

    elif status == "UNKNOWN":
        reason = (
            "Order status could not be recognized"
        )

    else:
        reason = (
            f"Order status is {status}"
        )

    return {
        "status": (
            "verified"
            if verified
            else "unverified"
        ),
        "verified": verified,
        "execution_success": execution_success,
        "filled": filled,
        "partially_filled": partially_filled,
        "terminal": terminal,
        "retry_required": retry_required,

        "symbol": symbol,
        "order_id": order_id,
        "client_order_id": (
            client_order_id or None
        ),
        "side": side,
        "order_type": order_type,
        "order_status": status,

        "original_quantity": round(
            original_quantity,
            12,
        ),
        "filled_quantity": round(
            executed_quantity,
            12,
        ),
        "remaining_quantity": round(
            remaining_quantity,
            12,
        ),
        "average_price": round(
            average_price,
            12,
        ),

        "reduce_only": reduce_only,
        "attempts": attempts,
        "verification_source": source,
        "query_error": query_error,
        "reason": reason,
        "raw_order": order,
    }


def query_futures_order(
    symbol: str,
    order_id: int | None = None,
    client_order_id: str | None = None,
) -> dict:
    """
    Query one Binance USD-M Futures order.

    Either order_id or client_order_id must be provided.
    """

    symbol = _safe_text(
        symbol
    ).upper()

    if not symbol:
        raise ValueError(
            "Symbol is required"
        )

    if order_id is None and not client_order_id:
        raise ValueError(
            "order_id or client_order_id is required"
        )

    if order_id is not None:
        return client.query_order(
            symbol=symbol,
            orderId=int(order_id),
        )

    return client.query_order(
        symbol=symbol,
        origClientOrderId=str(
            client_order_id
        ),
    )


def verify_order_response(
    order_response: dict | None,
) -> dict:
    """
    Validate only the immediate response returned by new_order().
    No additional Binance query is performed.
    """

    if not isinstance(order_response, dict):
        return {
            "status": "invalid",
            "verified": False,
            "execution_success": False,
            "filled": False,
            "partially_filled": False,
            "terminal": False,
            "retry_required": False,
            "order_status": "UNKNOWN",
            "attempts": 0,
            "verification_source": "INITIAL_RESPONSE",
            "query_error": None,
            "reason": (
                "Order response is missing or is not a dictionary"
            ),
            "raw_order": order_response,
        }

    return _build_verification_result(
        order=order_response,
        attempts=0,
        source="INITIAL_RESPONSE",
    )


def verify_futures_order(
    symbol: str,
    order_response: dict | None = None,
    order_id: int | None = None,
    client_order_id: str | None = None,
    max_attempts: int = 5,
    initial_delay_seconds: float = 0.5,
    backoff_multiplier: float = 1.8,
    stop_when_terminal: bool = True,
) -> dict:
    """
    Query Binance repeatedly and verify the final known order state.

    The immediate order response can be supplied so order identifiers
    are extracted automatically.
    """

    symbol = _safe_text(
        symbol
    ).upper()

    order_response = (
        order_response
        if isinstance(order_response, dict)
        else {}
    )

    resolved_order_id = (
        order_id
        if order_id is not None
        else _extract_order_id(order_response)
    )

    resolved_client_order_id = (
        client_order_id
        or _extract_client_order_id(
            order_response
        )
    )

    safe_max_attempts = _safe_int(
        max_attempts,
        5,
    )

    max_attempts = max(
        1,
        min(
            20,
            safe_max_attempts or 5,
        ),
    )

    delay = max(
        0.0,
        _safe_float(
            initial_delay_seconds,
            0.5,
        ),
    )

    backoff_multiplier = max(
        1.0,
        _safe_float(
            backoff_multiplier,
            1.8,
        ),
    )

    if not symbol:
        return {
            "status": "invalid",
            "verified": False,
            "execution_success": False,
            "filled": False,
            "partially_filled": False,
            "terminal": False,
            "retry_required": False,
            "order_status": "UNKNOWN",
            "attempts": 0,
            "verification_source": "BINANCE_QUERY",
            "query_error": None,
            "reason": "Symbol is missing",
            "raw_order": order_response,
        }

    if (
        resolved_order_id is None
        and not resolved_client_order_id
    ):
        initial_result = verify_order_response(
            order_response
        )

        initial_result["status"] = "invalid"
        initial_result["verified"] = False
        initial_result["reason"] = (
            "No order ID or client order ID is available "
            "for Binance verification"
        )

        return initial_result

    latest_order = order_response
    latest_error = None
    attempts_completed = 0

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        attempts_completed = attempt

        try:
            latest_order = query_futures_order(
                symbol=symbol,
                order_id=resolved_order_id,
                client_order_id=(
                    resolved_client_order_id
                ),
            )

            latest_error = None

            result = _build_verification_result(
                order=latest_order,
                attempts=attempt,
                source="BINANCE_QUERY",
            )

            if (
                result["filled"]
                or (
                    stop_when_terminal
                    and result["terminal"]
                )
            ):
                return result

            if attempt < max_attempts:
                time.sleep(delay)

                delay *= backoff_multiplier

        except Exception as error:
            latest_error = str(error)

            should_retry = (
                _is_retryable_exception(error)
                and attempt < max_attempts
            )

            if not should_retry:
                break

            time.sleep(delay)

            delay *= backoff_multiplier

    if isinstance(latest_order, dict) and latest_order:
        result = _build_verification_result(
            order=latest_order,
            attempts=attempts_completed,
            source=(
                "BINANCE_QUERY"
                if latest_order is not order_response
                else "INITIAL_RESPONSE"
            ),
            query_error=latest_error,
        )

        if latest_error:
            result["retry_required"] = True

        return result

    return {
        "status": "query_failed",
        "verified": False,
        "execution_success": False,
        "filled": False,
        "partially_filled": False,
        "terminal": False,
        "retry_required": True,

        "symbol": symbol,
        "order_id": resolved_order_id,
        "client_order_id": (
            resolved_client_order_id
        ),
        "side": None,
        "order_type": None,
        "order_status": "UNKNOWN",

        "original_quantity": 0.0,
        "filled_quantity": 0.0,
        "remaining_quantity": 0.0,
        "average_price": 0.0,

        "reduce_only": False,
        "attempts": attempts_completed,
        "verification_source": "BINANCE_QUERY",
        "query_error": latest_error,
        "reason": (
            "Unable to verify the order from Binance"
        ),
        "raw_order": latest_order,
    }


def verify_execution_result(
    execution: dict | None,
    max_attempts: int = 5,
    initial_delay_seconds: float = 0.5,
) -> dict:
    """
    Verify an execution dictionary returned by execute_testnet_trade().
    """

    execution = execution or {}

    execution_status = _safe_text(
        execution.get("status")
    ).lower()

    submitted = execution.get("submitted") is True

    valid_execution_statuses = {
        "executed",
        "submitted",
        "submitted_unverified",
    }

    if (
        execution_status not in valid_execution_statuses
        and not submitted
    ):
        return {
            "status": "not_executed",
            "verified": False,
            "execution_success": False,
            "filled": False,
            "partially_filled": False,
            "terminal": False,
            "retry_required": False,
            "order_status": "NOT_SUBMITTED",
            "attempts": 0,
            "verification_source": "EXECUTION_RESULT",
            "query_error": None,
            "reason": (
                "Execution result does not contain a submitted order"
            ),
            "raw_order": execution.get("order"),
        }

    symbol = _safe_text(
        execution.get("symbol")
    ).upper()

    order_response = execution.get("order")

    return verify_futures_order(
        symbol=symbol,
        order_response=order_response,
        max_attempts=max_attempts,
        initial_delay_seconds=(
            initial_delay_seconds
        ),
    )