"""TitanAI Portfolio Exposure Manager v26."""

from __future__ import annotations

from typing import Any


DEFAULT_CORRELATION_GROUPS = (
    {
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "BNBUSDT",
        "XRPUSDT",
        "ADAUSDT",
        "DOGEUSDT",
    },
)


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)
        if result != result:
            return default
        if result in {
            float("inf"),
            float("-inf"),
        }:
            return default
        return result
    except (TypeError, ValueError):
        return default


def _position_notional(position: dict) -> float:
    direct = abs(
        _safe_float(
            position.get(
                "notional",
                position.get("notionalValue"),
            )
        )
    )

    if direct > 0:
        return direct

    amount = abs(
        _safe_float(
            position.get(
                "positionAmt",
                position.get("position_amount"),
            )
        )
    )
    mark = _safe_float(
        position.get(
            "markPrice",
            position.get("mark_price"),
        )
    )

    return amount * mark


def evaluate_portfolio_exposure(
    *,
    balance: float,
    proposed_symbol: str,
    proposed_side: str,
    proposed_position_usdt: float,
    open_positions: list[dict] | None,
    maximum_total_exposure_percent: float = 25.0,
    maximum_concurrent_positions: int = 1,
    block_correlated_same_direction: bool = True,
) -> dict:
    balance = max(0.0, _safe_float(balance))
    proposed_symbol = str(
        proposed_symbol or ""
    ).upper()
    proposed_side = str(
        proposed_side or ""
    ).upper()
    proposed_position_usdt = max(
        0.0,
        _safe_float(proposed_position_usdt),
    )

    active_positions = []

    for position in open_positions or []:
        if not isinstance(position, dict):
            continue

        amount = _safe_float(
            position.get(
                "positionAmt",
                position.get("position_amount"),
            )
        )

        if amount == 0:
            continue

        active_positions.append(
            {
                "symbol": str(
                    position.get("symbol", "")
                ).upper(),
                "side": (
                    "BUY"
                    if amount > 0
                    else "SELL"
                ),
                "notional": _position_notional(
                    position
                ),
            }
        )

    current_exposure = sum(
        item["notional"]
        for item in active_positions
    )

    maximum_total_exposure = (
        balance
        * max(
            0.0,
            min(
                100.0,
                _safe_float(
                    maximum_total_exposure_percent,
                    25.0,
                ),
            ),
        )
        / 100.0
    )

    projected_exposure = (
        current_exposure
        + proposed_position_usdt
    )

    block_reasons = []

    if (
        len(active_positions)
        >= max(1, int(maximum_concurrent_positions))
    ):
        block_reasons.append(
            "Maximum concurrent-position limit reached"
        )

    if (
        maximum_total_exposure > 0
        and projected_exposure
        > maximum_total_exposure + 1e-9
    ):
        block_reasons.append(
            "Projected portfolio exposure exceeds configured maximum"
        )

    if block_correlated_same_direction:
        for group in DEFAULT_CORRELATION_GROUPS:
            if proposed_symbol not in group:
                continue

            if any(
                item["symbol"] in group
                and item["side"] == proposed_side
                for item in active_positions
            ):
                block_reasons.append(
                    "Correlated same-direction exposure already exists"
                )
                break

    return {
        "status": "ready",
        "version": "v26",
        "allowed": len(block_reasons) == 0,
        "active_position_count": len(
            active_positions
        ),
        "current_exposure_usdt": round(
            current_exposure,
            8,
        ),
        "proposed_position_usdt": round(
            proposed_position_usdt,
            8,
        ),
        "projected_exposure_usdt": round(
            projected_exposure,
            8,
        ),
        "maximum_total_exposure_usdt": round(
            maximum_total_exposure,
            8,
        ),
        "open_positions": active_positions,
        "block_reasons": list(
            dict.fromkeys(block_reasons)
        ),
    }
