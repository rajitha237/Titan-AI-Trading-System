"""Order consistency audit v28."""

from __future__ import annotations

from typing import Any


PROTECTION_ORDER_TYPES = {
    "STOP",
    "STOP_MARKET",
    "TAKE_PROFIT",
    "TAKE_PROFIT_MARKET",
    "TRAILING_STOP_MARKET",
}


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)

        if (
            number != number
            or number
            in {
                float("inf"),
                float("-inf"),
            }
        ):
            return default

        return number

    except (TypeError, ValueError):
        return default


def normalise_exchange_order(
    order: Any,
) -> dict | None:
    if not isinstance(order, dict):
        return None

    symbol = str(
        order.get("symbol", "")
    ).strip().upper()
    side = str(
        order.get("side", "")
    ).strip().upper()
    order_type = str(
        order.get(
            "type",
            order.get("orderType", ""),
        )
    ).strip().upper()
    order_id = order.get(
        "orderId",
        order.get("algoId"),
    )
    client_order_id = order.get(
        "clientOrderId",
        order.get("clientAlgoId"),
    )
    is_algo_order = bool(
        order.get("isAlgoOrder", False)
        or order.get("algoId") is not None
    )

    if (
        not symbol
        or side not in {
            "BUY",
            "SELL",
        }
        or (
            order_id in {
                None,
                "",
            }
            and not client_order_id
        )
    ):
        return None

    identity = (
        str(order_id)
        if order_id not in {
            None,
            "",
        }
        else str(client_order_id)
    )

    order_key = (
        f"{symbol}:"
        f"{'ALGO' if is_algo_order else 'NORMAL'}:"
        f"{identity}"
    )

    return {
        "order_key": order_key,
        "symbol": symbol,
        "order_id": (
            str(order_id)
            if order_id not in {
                None,
                "",
            }
            else None
        ),
        "client_order_id": (
            str(client_order_id)
            if client_order_id
            else None
        ),
        "order_type": (
            order_type or "UNKNOWN"
        ),
        "side": side,
        "status": str(
            order.get("status", "NEW")
        ).upper(),
        "reduce_only": bool(
            order.get("reduceOnly", False)
        ),
        "is_algo_order": is_algo_order,
        "quantity": abs(
            _safe_float(
                order.get(
                    "origQty",
                    order.get(
                        "quantity",
                        0.0,
                    ),
                )
            )
        ),
        "price": _safe_float(
            order.get("price")
        ),
        "stop_price": _safe_float(
            order.get(
                "stopPrice",
                order.get(
                    "triggerPrice",
                    0.0,
                ),
            )
        ),
        "metadata": {
            "working_type": (
                order.get("workingType")
            ),
            "position_side": (
                order.get("positionSide")
            ),
            "time_in_force": (
                order.get("timeInForce")
            ),
        },
        "raw": order,
    }


def build_order_consistency_audit(
    *,
    exchange_orders: list[dict] | None,
    local_open_orders: list[dict] | None,
    open_positions: list[dict] | None,
) -> dict:
    normalised_orders = []

    for order in exchange_orders or []:
        normalised = (
            normalise_exchange_order(
                order
            )
        )

        if normalised is not None:
            normalised_orders.append(
                normalised
            )

    local_orders = [
        order
        for order in (
            local_open_orders or []
        )
        if isinstance(order, dict)
        and str(
            order.get("status", "OPEN")
        ).upper()
        == "OPEN"
    ]

    exchange_by_key = {
        order["order_key"]: order
        for order in normalised_orders
    }
    local_by_key = {
        str(
            order.get("order_key")
        ): order
        for order in local_orders
        if order.get("order_key")
    }

    exchange_keys = set(
        exchange_by_key
    )
    local_keys = set(local_by_key)

    missing_local = sorted(
        exchange_keys - local_keys
    )
    missing_exchange = sorted(
        local_keys - exchange_keys
    )

    duplicate_orders = []
    seen = set()

    for order in normalised_orders:
        key = order["order_key"]

        if key in seen:
            duplicate_orders.append(
                key
            )

        seen.add(key)

    open_position_symbols = {
        str(
            position.get("symbol", "")
        ).upper()
        for position in (
            open_positions or []
        )
        if isinstance(position, dict)
    }

    orphan_reduce_only_orders = []
    unsafe_protection_orders = []

    for order in normalised_orders:
        if (
            order["reduce_only"]
            and order["symbol"]
            not in open_position_symbols
        ):
            orphan_reduce_only_orders.append(
                order["order_key"]
            )

        if (
            order["order_type"]
            in PROTECTION_ORDER_TYPES
            and not order["reduce_only"]
        ):
            unsafe_protection_orders.append(
                order["order_key"]
            )

    issue_count = (
        len(missing_local)
        + len(missing_exchange)
        + len(duplicate_orders)
        + len(orphan_reduce_only_orders)
        + len(unsafe_protection_orders)
    )

    return {
        "status": (
            "consistent"
            if issue_count == 0
            else "drift_detected"
        ),
        "version": "v28",
        "diagnostics_only": True,
        "exchange_open_order_count": (
            len(normalised_orders)
        ),
        "local_open_order_count": (
            len(local_orders)
        ),
        "missing_local_orders": [
            exchange_by_key[key]
            for key in missing_local
        ],
        "missing_exchange_orders": [
            local_by_key[key]
            for key in missing_exchange
        ],
        "duplicate_exchange_orders": (
            duplicate_orders
        ),
        "orphan_reduce_only_orders": (
            orphan_reduce_only_orders
        ),
        "unsafe_protection_orders": (
            unsafe_protection_orders
        ),
        "issue_count": issue_count,
    }
