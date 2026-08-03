"""
TitanAI Safe Testnet Executor v3

Executes Binance Futures Testnet market orders and immediately verifies
the resulting order through the Order Verification Engine.

Safety features:
- Explicit execute_trade flag required
- BUY / SELL decisions only
- Missing, zero and invalid quantity protection
- Symbol validation
- Binance order-response validation
- Automatic order-status verification
- Filled / partially-filled / pending / failed-state reporting
- Safe verification parameter normalisation
- Consistent execution response structure
- Exception handling without crashing the full trading cycle
- Fail-closed behaviour when Binance returns an invalid response
"""

from math import isfinite
from typing import Any

from app.exchange.binance_testnet_client import (
    place_test_market_order,
)
from app.trader.order_verification_engine import (
    verify_execution_result,
)


VALID_DECISIONS = {
    "BUY",
    "SELL",
}

TESTNET_MODE = "TESTNET"
SAFETY_LOCKED_MODE = "SAFETY_LOCKED"


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    """
    Safely convert a value to a finite float.
    """
    try:
        result = float(value)

        if not isfinite(result):
            return default

        return result

    except (TypeError, ValueError, OverflowError):
        return default


def _safe_int(
    value: Any,
    default: int = 1,
    minimum: int = 1,
    maximum: int | None = None,
) -> int:
    """
    Safely convert a value to an integer and clamp it to a safe range.
    """
    try:
        result = int(value)

    except (TypeError, ValueError, OverflowError):
        result = default

    result = max(
        minimum,
        result,
    )

    if maximum is not None:
        result = min(
            maximum,
            result,
        )

    return result


def _get_decision(
    final_decision: dict | None,
) -> str:
    """
    Extract and normalise the trade decision.
    """
    if not isinstance(
        final_decision,
        dict,
    ):
        final_decision = {}

    decision = final_decision.get(
        "decision",
        final_decision.get(
            "signal",
            "HOLD",
        ),
    )

    return str(
        decision or "HOLD"
    ).upper().strip()


def _normalise_symbol(
    symbol: Any,
) -> str:
    """
    Normalise a Binance symbol.
    """
    return str(
        symbol or ""
    ).upper().strip()


def _not_required_verification(
    reason: str,
) -> dict:
    """
    Build a verification response for an order that was not submitted.
    """
    return {
        "status": "not_required",
        "verified": False,
        "execution_success": False,
        "filled": False,
        "partially_filled": False,
        "terminal": False,
        "retry_required": False,
        "order_status": "NOT_SUBMITTED",
        "filled_quantity": 0.0,
        "remaining_quantity": 0.0,
        "average_price": 0.0,
        "reason": reason,
    }


def _blocked_response(
    *,
    reason: str,
    decision: str,
    symbol: str,
    quantity: float,
) -> dict:
    """
    Build a consistent safety-blocked response.
    """
    return {
        "status": "blocked",
        "reason": reason,
        "decision": decision,
        "side": decision,
        "symbol": symbol,
        "quantity": quantity,
        "submitted": False,
        "mode": SAFETY_LOCKED_MODE,
        "order": None,
        "verification": _not_required_verification(
            "Order validation failed before submission"
        ),
        "filled_quantity": 0.0,
        "remaining_quantity": quantity,
        "average_fill_price": 0.0,
        "order_status": "NOT_SUBMITTED",
    }


def _validate_order_response(
    order: Any,
) -> tuple[bool, str]:
    """
    Validate the Binance market-order response before verification.

    Binance normally returns an orderId for a successfully accepted
    Futures order. A clientOrderId may also be present.
    """
    if not isinstance(
        order,
        dict,
    ):
        return (
            False,
            "Binance returned a non-dictionary order response",
        )

    if order.get("code") is not None:
        error_code = order.get(
            "code"
        )
        error_message = order.get(
            "msg",
            "Unknown Binance error",
        )

        return (
            False,
            (
                "Binance returned an error response: "
                f"{error_code} - {error_message}"
            ),
        )

    order_id = order.get(
        "orderId"
    )

    client_order_id = order.get(
        "clientOrderId"
    )

    if order_id in (
        None,
        "",
        0,
        "0",
    ) and not client_order_id:
        return (
            False,
            "Binance order response does not contain an order identifier",
        )

    return (
        True,
        "Binance order response is valid",
    )


def _verification_error_response(
    error: Exception,
) -> dict:
    """
    Build a safe response when order verification raises an exception.
    """
    return {
        "status": "verification_failed",
        "verified": False,
        "execution_success": False,
        "filled": False,
        "partially_filled": False,
        "terminal": False,
        "retry_required": True,
        "order_status": "UNKNOWN",
        "filled_quantity": 0.0,
        "remaining_quantity": 0.0,
        "average_price": 0.0,
        "query_error": str(
            error
        ),
        "reason": (
            "Order was submitted, but verification raised an error"
        ),
    }


def execute_testnet_trade(
    final_decision: dict,
    symbol: str,
    quantity: float | None = None,
    execute_trade: bool = False,
    verify_order: bool = True,
    verification_attempts: int = 5,
    verification_delay_seconds: float = 0.5,
) -> dict:
    """
    Submit and verify one Binance Futures Testnet market order.

    The caller must explicitly provide:
    - execute_trade=True
    - BUY or SELL decision
    - valid symbol
    - positive quantity

    This function never retries order submission automatically because
    retrying a market-order request could create a duplicate position.
    Verification may retry order-status queries safely.
    """
    decision = _get_decision(
        final_decision
    )

    safe_symbol = _normalise_symbol(
        symbol
    )

    safe_quantity = _safe_float(
        quantity,
        0.0,
    )

    safe_verification_attempts = _safe_int(
        verification_attempts,
        default=5,
        minimum=1,
        maximum=20,
    )

    safe_verification_delay = max(
        0.0,
        min(
            _safe_float(
                verification_delay_seconds,
                0.5,
            ),
            30.0,
        ),
    )

    if execute_trade is not True:
        return {
            "status": "skipped",
            "reason": "execute_trade flag is false",
            "decision": decision,
            "side": decision,
            "symbol": safe_symbol,
            "quantity": safe_quantity,
            "submitted": False,
            "mode": SAFETY_LOCKED_MODE,
            "order": None,
            "verification": _not_required_verification(
                "No order was submitted"
            ),
            "filled_quantity": 0.0,
            "remaining_quantity": safe_quantity,
            "average_fill_price": 0.0,
            "order_status": "NOT_SUBMITTED",
        }

    if not safe_symbol:
        return _blocked_response(
            reason="Symbol is missing",
            decision=decision,
            symbol=safe_symbol,
            quantity=safe_quantity,
        )

    if decision not in VALID_DECISIONS:
        return _blocked_response(
            reason=(
                f"Decision is {decision}, not BUY or SELL"
            ),
            decision=decision,
            symbol=safe_symbol,
            quantity=safe_quantity,
        )

    if safe_quantity <= 0:
        return _blocked_response(
            reason="Quantity must be greater than zero",
            decision=decision,
            symbol=safe_symbol,
            quantity=safe_quantity,
        )

    try:
        order = place_test_market_order(
            symbol=safe_symbol,
            side=decision,
            quantity=safe_quantity,
        )

    except Exception as error:
        return {
            "status": "failed",
            "reason": (
                "Binance Testnet order submission failed"
            ),
            "decision": decision,
            "side": decision,
            "symbol": safe_symbol,
            "quantity": safe_quantity,
            "submitted": False,
            "mode": TESTNET_MODE,
            "error": str(
                error
            ),
            "order": None,
            "verification": {
                "status": "not_executed",
                "verified": False,
                "execution_success": False,
                "filled": False,
                "partially_filled": False,
                "terminal": True,
                "retry_required": False,
                "order_status": "SUBMISSION_FAILED",
                "filled_quantity": 0.0,
                "remaining_quantity": safe_quantity,
                "average_price": 0.0,
                "reason": (
                    "Order submission failed before verification"
                ),
            },
            "filled_quantity": 0.0,
            "remaining_quantity": safe_quantity,
            "average_fill_price": 0.0,
            "order_status": "SUBMISSION_FAILED",
        }

    order_response_valid, order_response_reason = (
        _validate_order_response(
            order
        )
    )

    if not order_response_valid:
        return {
            "status": "failed",
            "reason": order_response_reason,
            "decision": decision,
            "side": decision,
            "symbol": safe_symbol,
            "quantity": safe_quantity,
            "submitted": False,
            "mode": TESTNET_MODE,
            "order": order,
            "verification": {
                "status": "invalid_order_response",
                "verified": False,
                "execution_success": False,
                "filled": False,
                "partially_filled": False,
                "terminal": True,
                "retry_required": False,
                "order_status": "INVALID_RESPONSE",
                "filled_quantity": 0.0,
                "remaining_quantity": safe_quantity,
                "average_price": 0.0,
                "reason": order_response_reason,
            },
            "filled_quantity": 0.0,
            "remaining_quantity": safe_quantity,
            "average_fill_price": 0.0,
            "order_status": "INVALID_RESPONSE",
        }

    execution = {
        "status": "submitted",
        "reason": (
            "Testnet market order was submitted"
        ),
        "symbol": safe_symbol,
        "side": decision,
        "decision": decision,
        "quantity": safe_quantity,
        "submitted": True,
        "mode": TESTNET_MODE,
        "order": order,
        "order_id": order.get(
            "orderId"
        ),
        "client_order_id": order.get(
            "clientOrderId"
        ),
    }

    if verify_order is not True:
        execution.update(
            {
                "status": "submitted_unverified",
                "reason": (
                    "Testnet order was submitted, but automatic "
                    "verification is disabled"
                ),
                "verification": {
                    "status": "skipped",
                    "verified": False,
                    "execution_success": True,
                    "filled": False,
                    "partially_filled": False,
                    "terminal": False,
                    "retry_required": True,
                    "order_status": str(
                        order.get(
                            "status",
                            "UNKNOWN",
                        )
                    ).upper(),
                    "filled_quantity": _safe_float(
                        order.get(
                            "executedQty"
                        ),
                        0.0,
                    ),
                    "remaining_quantity": safe_quantity,
                    "average_price": _safe_float(
                        order.get(
                            "avgPrice"
                        ),
                        0.0,
                    ),
                    "reason": (
                        "Automatic order verification is disabled"
                    ),
                },
            }
        )

        verification = execution[
            "verification"
        ]

        execution["filled_quantity"] = _safe_float(
            verification.get(
                "filled_quantity"
            ),
            0.0,
        )

        execution["remaining_quantity"] = max(
            0.0,
            safe_quantity
            - execution[
                "filled_quantity"
            ],
        )

        execution["average_fill_price"] = _safe_float(
            verification.get(
                "average_price"
            ),
            0.0,
        )

        execution["order_status"] = str(
            verification.get(
                "order_status",
                "UNKNOWN",
            )
        ).upper()

        return execution

    try:
        verification = verify_execution_result(
            execution=execution,
            max_attempts=safe_verification_attempts,
            initial_delay_seconds=safe_verification_delay,
        )

        if not isinstance(
            verification,
            dict,
        ):
            raise RuntimeError(
                "Order Verification Engine returned a non-dictionary response"
            )

    except Exception as error:
        verification = _verification_error_response(
            error
        )

        verification[
            "remaining_quantity"
        ] = safe_quantity

    execution[
        "verification"
    ] = verification

    filled_quantity = _safe_float(
        verification.get(
            "filled_quantity"
        ),
        0.0,
    )

    remaining_quantity = _safe_float(
        verification.get(
            "remaining_quantity"
        ),
        max(
            0.0,
            safe_quantity - filled_quantity,
        ),
    )

    average_fill_price = _safe_float(
        verification.get(
            "average_price",
            verification.get(
                "average_fill_price",
                0.0,
            ),
        ),
        0.0,
    )

    order_status = str(
        verification.get(
            "order_status",
            "UNKNOWN",
        )
    ).upper().strip()

    execution[
        "filled_quantity"
    ] = filled_quantity

    execution[
        "remaining_quantity"
    ] = max(
        0.0,
        remaining_quantity,
    )

    execution[
        "average_fill_price"
    ] = average_fill_price

    execution[
        "order_status"
    ] = order_status

    if verification.get(
        "filled"
    ) is True:
        execution[
            "status"
        ] = "verified_filled"

        execution[
            "reason"
        ] = (
            "Testnet order was submitted and filled"
        )

    elif verification.get(
        "partially_filled"
    ) is True:
        execution[
            "status"
        ] = "verified_partially_filled"

        execution[
            "reason"
        ] = (
            "Testnet order was partially filled"
        )

    elif (
        verification.get(
            "terminal"
        )
        is True
        and verification.get(
            "execution_success"
        )
        is not True
    ):
        execution[
            "status"
        ] = "verified_failed"

        execution[
            "reason"
        ] = (
            "Testnet order reached a terminal failure state"
        )

    elif verification.get(
        "verified"
    ) is True:
        execution[
            "status"
        ] = "verified_pending"

        execution[
            "reason"
        ] = (
            "Testnet order was accepted and is still pending"
        )

    else:
        execution[
            "status"
        ] = "verification_pending"

        execution[
            "reason"
        ] = (
            "Testnet order was submitted but could not yet be verified"
        )

    return execution