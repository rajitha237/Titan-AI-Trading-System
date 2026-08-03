"""
TitanAI Trade Builder v2

Converts an approved AI setup and risk plan into a safe trade plan.

Responsibilities:
- Validate BUY / SELL decision
- Require Confirmation Engine approval
- Require Risk Engine approval
- Calculate dynamic quantity
- Calculate entry, stop-loss, and take-profit prices
- Protect against zero or invalid quantities
- Return execution-ready Binance order parameters

This module does not send orders to Binance.
"""

from decimal import Decimal, InvalidOperation, ROUND_CEILING
from math import isfinite
from typing import Any

from app.trader.quantity_calculator import (
    calculate_trade_quantity,
)


VALID_SIDES = {"BUY", "SELL"}


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



def _safe_decimal(
    value: Any,
    default: str = "0",
) -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite():
            return Decimal(default)
        return result
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _ceil_to_step(
    value: float,
    step_size: float,
) -> float:
    value_decimal = _safe_decimal(value)
    step_decimal = _safe_decimal(step_size)

    if value_decimal <= 0:
        return 0.0

    if step_decimal <= 0:
        return float(value_decimal)

    steps = (
        value_decimal / step_decimal
    ).to_integral_value(rounding=ROUND_CEILING)

    return float(steps * step_decimal)


def _apply_exchange_quantity_rules(
    *,
    quantity: float,
    entry_price: float,
    position_size_usdt: float,
    exchange_filters: dict | None,
    allow_quantity_increase: bool,
) -> tuple[float, dict, list[str], list[str]]:
    """
    Validate the actual order notional against Binance filters.

    Quantity is increased only when the next valid step still remains inside
    the Risk Engine-approved position size. Otherwise the candidate is blocked
    so the runner can try the next ranked symbol.
    """
    filters = exchange_filters or {}
    warnings: list[str] = []
    block_reasons: list[str] = []

    min_notional = _safe_float(filters.get("min_notional"), 0.0)
    min_qty = _safe_float(filters.get("min_qty"), 0.0)
    step_size = _safe_float(filters.get("step_size"), 0.0)

    adjusted_quantity = _safe_float(quantity, 0.0)
    actual_notional = adjusted_quantity * entry_price

    required_quantity = 0.0
    required_notional = 0.0
    quantity_adjusted = False

    if min_qty > 0 and adjusted_quantity < min_qty:
        required_quantity = _ceil_to_step(min_qty, step_size)
        required_notional = required_quantity * entry_price

        if (
            allow_quantity_increase
            and required_notional <= position_size_usdt + 1e-9
        ):
            adjusted_quantity = required_quantity
            actual_notional = required_notional
            quantity_adjusted = True
            warnings.append(
                "Quantity increased to satisfy exchange minimum quantity "
                "without exceeding approved position size"
            )
        else:
            block_reasons.append(
                "Calculated quantity is below the exchange minimum quantity"
            )

    if min_notional > 0 and actual_notional + 1e-9 < min_notional:
        minimum_notional_quantity = _ceil_to_step(
            min_notional / entry_price,
            step_size,
        )
        minimum_notional_quantity = max(
            minimum_notional_quantity,
            _ceil_to_step(min_qty, step_size) if min_qty > 0 else 0.0,
        )
        required_quantity = max(
            required_quantity,
            minimum_notional_quantity,
        )
        required_notional = required_quantity * entry_price

        if (
            allow_quantity_increase
            and required_quantity > adjusted_quantity
            and required_notional <= position_size_usdt + 1e-9
        ):
            adjusted_quantity = required_quantity
            actual_notional = required_notional
            quantity_adjusted = True
            warnings.append(
                "Quantity increased to satisfy exchange minimum notional "
                "without exceeding approved position size"
            )
        else:
            block_reasons.append(
                "Actual order notional is below the exchange minimum; "
                "the next valid quantity step would exceed the approved "
                "position size"
            )

    exchange_validation = {
        "checked": bool(exchange_filters),
        "min_notional": round(min_notional, 10),
        "min_qty": round(min_qty, 10),
        "step_size": round(step_size, 10),
        "actual_order_notional": round(actual_notional, 10),
        "required_quantity": round(required_quantity, 10),
        "required_notional": round(required_notional, 10),
        "quantity_adjusted": quantity_adjusted,
    }

    return (
        adjusted_quantity,
        exchange_validation,
        block_reasons,
        warnings,
    )


def _get_decision(
    final_decision: dict | None,
) -> str:
    final_decision = final_decision or {}

    decision = str(
        final_decision.get(
            "decision",
            final_decision.get("signal", "HOLD"),
        )
    ).upper()

    return decision


def _get_confirmation_status(
    confirmation: dict | None,
) -> tuple[bool, str, float]:
    confirmation = confirmation or {}

    passed = bool(
        confirmation.get("passed", False)
    )

    decision = str(
        confirmation.get("decision", "UNKNOWN")
    ).upper()

    score = _safe_float(
        confirmation.get("confirmation_score"),
        0.0,
    )

    approved = (
        passed
        and decision == "APPROVE"
    )

    return approved, decision, score


def _get_risk_status(
    risk_plan: dict | None,
) -> tuple[bool, bool]:
    risk_plan = risk_plan or {}

    approved = bool(
        risk_plan.get("approved", False)
    )

    execution_allowed = bool(
        risk_plan.get("execution_allowed", False)
    )

    return approved, execution_allowed


def _calculate_exit_prices(
    side: str,
    entry_price: float,
    stop_loss_percent: float,
    take_profit_percent: float,
) -> tuple[float, float]:
    if side == "BUY":
        stop_loss_price = entry_price * (
            1 - stop_loss_percent / 100
        )

        take_profit_price = entry_price * (
            1 + take_profit_percent / 100
        )

    else:
        stop_loss_price = entry_price * (
            1 + stop_loss_percent / 100
        )

        take_profit_price = entry_price * (
            1 - take_profit_percent / 100
        )

    return stop_loss_price, take_profit_price


def build_trade_plan(
    symbol: str,
    price: float,
    final_decision: dict,
    confirmation: dict,
    risk_plan: dict,
    quantity: float | None = None,
    exchange_filters: dict | None = None,
) -> dict:
    block_reasons = []
    warnings = []

    symbol = str(symbol or "").upper().strip()
    entry_price = _safe_float(price)

    side = _get_decision(
        final_decision
    )

    confirmation_approved, confirmation_decision, (
        confirmation_score
    ) = _get_confirmation_status(
        confirmation
    )

    risk_approved, risk_execution_allowed = (
        _get_risk_status(
            risk_plan
        )
    )

    if not symbol:
        block_reasons.append(
            "Symbol is missing"
        )

    if side not in VALID_SIDES:
        block_reasons.append(
            f"Trade decision is {side}, not BUY or SELL"
        )

    if entry_price <= 0:
        block_reasons.append(
            "Entry price must be greater than zero"
        )

    if not confirmation_approved:
        block_reasons.append(
            "Confirmation Engine did not approve the trade"
        )

    if not risk_approved:
        block_reasons.append(
            "Risk Engine did not approve the trade"
        )

    if not risk_execution_allowed:
        block_reasons.append(
            "Risk Engine has execution disabled"
        )

    stop_loss_percent = _safe_float(
        risk_plan.get("stop_loss_percent"),
        0.0,
    )

    take_profit_percent = _safe_float(
        risk_plan.get("take_profit_percent"),
        0.0,
    )

    risk_reward_ratio = _safe_float(
        risk_plan.get("risk_reward_ratio"),
        0.0,
    )

    leverage = _safe_float(
        risk_plan.get("leverage"),
        1.0,
    )

    position_size_usdt = _safe_float(
        risk_plan.get(
            "position_size_usdt",
            risk_plan.get(
                "position_size",
                0.0,
            ),
        ),
        0.0,
    )

    margin_required = _safe_float(
        risk_plan.get("margin_required"),
        0.0,
    )

    risk_amount = _safe_float(
        risk_plan.get("risk_amount"),
        0.0,
    )

    if stop_loss_percent <= 0:
        block_reasons.append(
            "Stop-loss percentage is invalid"
        )

    if take_profit_percent <= 0:
        block_reasons.append(
            "Take-profit percentage is invalid"
        )

    if position_size_usdt <= 0:
        block_reasons.append(
            "Position size is zero or invalid"
        )

    if leverage < 1:
        block_reasons.append(
            "Leverage must be at least 1"
        )

    calculated_quantity = None
    quantity_source = "NOT_CALCULATED"
    quantity_error = None

    if not block_reasons:
        try:
            if quantity is None:
                calculated_quantity = (
                    calculate_trade_quantity(
                        symbol=symbol,
                        price=entry_price,
                        position_size_usdt=position_size_usdt,
                    )
                )

                quantity_source = "DYNAMIC"

            else:
                calculated_quantity = _safe_float(
                    quantity,
                    0.0,
                )

                quantity_source = "MANUAL"

        except Exception as error:
            quantity_error = str(error)

            block_reasons.append(
                f"Quantity calculation failed: {quantity_error}"
            )

    calculated_quantity = _safe_float(
        calculated_quantity,
        0.0,
    )

    if not block_reasons and calculated_quantity <= 0:
        block_reasons.append(
            "Calculated quantity is zero or invalid"
        )

    exchange_validation = {
        "checked": False,
        "min_notional": 0.0,
        "min_qty": 0.0,
        "step_size": 0.0,
        "actual_order_notional": round(
            calculated_quantity * entry_price,
            10,
        ),
        "required_quantity": 0.0,
        "required_notional": 0.0,
        "quantity_adjusted": False,
    }

    if not block_reasons and calculated_quantity > 0:
        (
            calculated_quantity,
            exchange_validation,
            exchange_blocks,
            exchange_warnings,
        ) = _apply_exchange_quantity_rules(
            quantity=calculated_quantity,
            entry_price=entry_price,
            position_size_usdt=position_size_usdt,
            exchange_filters=exchange_filters,
            allow_quantity_increase=(quantity is None),
        )
        block_reasons.extend(exchange_blocks)
        warnings.extend(exchange_warnings)

    stop_loss_price = 0.0
    take_profit_price = 0.0

    if (
        not block_reasons
        and side in VALID_SIDES
        and entry_price > 0
    ):
        (
            stop_loss_price,
            take_profit_price,
        ) = _calculate_exit_prices(
            side=side,
            entry_price=entry_price,
            stop_loss_percent=stop_loss_percent,
            take_profit_percent=take_profit_percent,
        )

    if side == "BUY":
        if (
            stop_loss_price > 0
            and stop_loss_price >= entry_price
        ):
            block_reasons.append(
                "BUY stop-loss must be below entry price"
            )

        if (
            take_profit_price > 0
            and take_profit_price <= entry_price
        ):
            block_reasons.append(
                "BUY take-profit must be above entry price"
            )

    elif side == "SELL":
        if (
            stop_loss_price > 0
            and stop_loss_price <= entry_price
        ):
            block_reasons.append(
                "SELL stop-loss must be above entry price"
            )

        if (
            take_profit_price > 0
            and take_profit_price >= entry_price
        ):
            block_reasons.append(
                "SELL take-profit must be below entry price"
            )

    block_reasons = list(
        dict.fromkeys(block_reasons)
    )

    warnings = list(
        dict.fromkeys(warnings)
    )

    ready = len(block_reasons) == 0

    return {
        "status": (
            "ready"
            if ready
            else "blocked"
        ),
        "ready": ready,
        "execution_allowed": ready,

        "symbol": symbol,
        "side": side,
        "order_type": "MARKET",

        "entry_price": round(
            entry_price,
            10,
        ),
        "quantity": calculated_quantity,
        "quantity_source": quantity_source,
        "quantity_error": quantity_error,
        "actual_order_notional": exchange_validation.get(
            "actual_order_notional",
            0.0,
        ),
        "exchange_validation": exchange_validation,

        "position_size_usdt": round(
            position_size_usdt,
            4,
        ),
        "margin_required": round(
            margin_required,
            4,
        ),
        "leverage": round(
            leverage,
            4,
        ),

        "stop_loss_price": round(
            stop_loss_price,
            10,
        ),
        "take_profit_price": round(
            take_profit_price,
            10,
        ),
        "stop_loss_percent": round(
            stop_loss_percent,
            4,
        ),
        "take_profit_percent": round(
            take_profit_percent,
            4,
        ),
        "risk_reward_ratio": round(
            risk_reward_ratio,
            4,
        ),
        "risk_amount": round(
            risk_amount,
            4,
        ),

        "confirmation": {
            "approved": confirmation_approved,
            "decision": confirmation_decision,
            "score": round(
                confirmation_score,
                2,
            ),
        },

        "risk": {
            "approved": risk_approved,
            "execution_allowed": (
                risk_execution_allowed
            ),
            "mode": risk_plan.get("mode"),
            "execution_mode": risk_plan.get(
                "execution_mode"
            ),
        },

        "reduce_only": False,
        "working_type": "MARK_PRICE",

        "block_reasons": block_reasons,
        "warnings": warnings,
    }