"""TitanAI v25 exact Binance trade lifecycle reconciliation."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.exchange.binance_testnet_client import (
    get_income_history,
    get_user_trades,
)
from app.trader.persistent_trade_state import (
    close_position_state,
    list_position_states,
    record_event,
    save_completed_trade,
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _milliseconds(value: datetime | None) -> int | None:
    return int(value.timestamp() * 1000) if value else None


def _active_keys(open_positions: list[dict]) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for position in open_positions or []:
        if not isinstance(position, dict):
            continue
        symbol = str(position.get("symbol", "")).upper()
        amount = _safe_float(
            position.get("positionAmt", position.get("position_amount", 0.0))
        )
        if symbol and amount:
            keys.add((symbol, "BUY" if amount > 0 else "SELL"))
    return keys


def _closing_side(position_side: str) -> str:
    return "SELL" if position_side == "BUY" else "BUY"


def _extract_exact_close(
    state: dict,
    *,
    closed_at: datetime,
) -> dict:
    symbol = state["symbol"]
    position_side = state["side"]
    close_side = _closing_side(position_side)
    opened_at = _parse_time(state.get("opened_at"))
    start_ms = _milliseconds(opened_at)
    end_ms = _milliseconds(closed_at)

    trades = get_user_trades(
        symbol,
        start_time=start_ms,
        end_time=end_ms,
        limit=1000,
    )
    closing = [
        trade for trade in trades
        if str(trade.get("side", "")).upper() == close_side
        and _safe_float(trade.get("qty")) > 0
    ]

    expected_quantity = max(
        _safe_float(state.get("original_quantity")),
        _safe_float(state.get("current_quantity")),
    )

    # Newest closing fills are most likely to belong to this just-closed position.
    closing.sort(key=lambda item: int(item.get("time", 0)), reverse=True)
    selected: list[dict] = []
    accumulated = 0.0
    for trade in closing:
        selected.append(trade)
        accumulated += _safe_float(trade.get("qty"))
        if expected_quantity <= 0 or accumulated + 1e-12 >= expected_quantity:
            break
    selected.sort(key=lambda item: int(item.get("time", 0)))

    if not selected:
        raise RuntimeError("No matching Binance closing fills were found")

    closed_quantity = sum(_safe_float(item.get("qty")) for item in selected)
    quote_quantity = sum(
        _safe_float(item.get("quoteQty"))
        or (
            _safe_float(item.get("price"))
            * _safe_float(item.get("qty"))
        )
        for item in selected
    )
    exit_price = quote_quantity / closed_quantity if closed_quantity > 0 else 0.0
    realized_pnl = sum(_safe_float(item.get("realizedPnl")) for item in selected)
    commission = sum(abs(_safe_float(item.get("commission"))) for item in selected)
    commission_assets = sorted({
        str(item.get("commissionAsset", "USDT")).upper()
        for item in selected
        if item.get("commissionAsset")
    })

    order_ids = sorted({
        str(item.get("orderId"))
        for item in selected
        if item.get("orderId") is not None
    })
    trade_ids = sorted({
        str(item.get("id"))
        for item in selected
        if item.get("id") is not None
    })

    income_audit = get_income_history(
        symbol=symbol,
        start_time=start_ms,
        end_time=end_ms,
        limit=1000,
    )
    relevant_income = [
        item for item in income_audit
        if str(item.get("incomeType", "")).upper()
        in {"REALIZED_PNL", "COMMISSION"}
    ]

    return {
        "exit_price": exit_price,
        "closed_quantity": closed_quantity,
        "gross_pnl": realized_pnl,
        "fees": commission,
        "net_pnl": realized_pnl - commission,
        "exit_price_source": "binance_user_trades",
        "closing_fills": selected,
        "closing_order_ids": order_ids,
        "closing_trade_ids": trade_ids,
        "commission_assets": commission_assets,
        "income_audit": relevant_income,
    }


def _infer_exit_reason(state: dict, exact: dict) -> str:
    metadata = state.get("metadata") or {}
    protection = metadata.get("last_protection_verification") or {}
    stop = _safe_float((protection.get("stop_loss_order") or {}).get("stop_price"))
    take = _safe_float(
        (protection.get("take_profit_order") or {}).get("stop_price")
    )
    exit_price = _safe_float(exact.get("exit_price"))
    side = state["side"]

    tolerance = max(exit_price * 0.0015, 0.00000001)
    if stop > 0 and abs(exit_price - stop) <= tolerance:
        return "STOP_LOSS"
    if take > 0 and abs(exit_price - take) <= tolerance:
        return "TAKE_PROFIT"
    if state.get("trailing_activated"):
        trailing = _safe_float(state.get("trailing_stop_price"))
        if trailing > 0 and abs(exit_price - trailing) <= tolerance:
            return "TRAILING_STOP"
    if state.get("break_even_moved"):
        entry = _safe_float(state.get("entry_price"))
        if abs(exit_price - entry) <= max(entry * 0.002, tolerance):
            return "BREAK_EVEN"
    return "MANUAL_OR_OTHER"


def reconcile_closed_positions(
    open_positions: list[dict],
    *,
    fee_rate_percent: float = 0.08,
) -> dict:
    """Journal persistent OPEN states that disappeared from Binance.

    v25 uses Binance account trades for exact exit price, exact realized PnL,
    exact commission, trade IDs, order IDs, and fill timestamps. The old
    estimate is retained only as a clearly marked fallback.
    """
    active = _active_keys(open_positions)
    completed: list[dict] = []
    errors: list[str] = []

    for state in list_position_states(status="OPEN"):
        if (state["symbol"], state["side"]) in active:
            continue

        closed_at = datetime.now(timezone.utc)
        source = "binance_user_trades"
        exact_error = None
        try:
            exact = _extract_exact_close(state, closed_at=closed_at)
        except Exception as error:
            exact_error = str(error)
            source = "estimated_last_mark_fallback"
            entry = _safe_float(state.get("entry_price"))
            exit_price = _safe_float(state.get("mark_price"), entry)
            quantity = max(
                _safe_float(state.get("original_quantity")),
                _safe_float(state.get("current_quantity")),
            )
            direction = 1.0 if state["side"] == "BUY" else -1.0
            gross = (exit_price - entry) * quantity * direction
            fees = (entry * quantity + exit_price * quantity) * (
                max(0.0, fee_rate_percent) / 100.0
            )
            exact = {
                "exit_price": exit_price,
                "closed_quantity": quantity,
                "gross_pnl": gross,
                "fees": fees,
                "net_pnl": gross - fees,
                "exit_price_source": source,
                "closing_fills": [],
                "closing_order_ids": [],
                "closing_trade_ids": [],
                "commission_assets": [],
                "income_audit": [],
            }

        try:
            entry = _safe_float(state["entry_price"])
            net_pnl = _safe_float(exact["net_pnl"])
            outcome = (
                "WIN" if net_pnl > 0 else
                "LOSS" if net_pnl < 0 else
                "BREAKEVEN"
            )
            exit_reason = _infer_exit_reason(state, exact)
            opened_at = _parse_time(state.get("opened_at"))
            duration = (
                max(0.0, (closed_at - opened_at).total_seconds())
                if opened_at else 0.0
            )
            fingerprint = ":".join([
                state["position_key"],
                ",".join(exact.get("closing_trade_ids", [])),
                str(int(closed_at.timestamp())),
            ])
            digest = hashlib.sha256(fingerprint.encode()).hexdigest()[:24]

            trade = save_completed_trade({
                "trade_id": f"trade-{digest}",
                "position_key": state["position_key"],
                "symbol": state["symbol"],
                "side": state["side"],
                "entry_price": entry,
                "exit_price": exact["exit_price"],
                "original_quantity": state.get("original_quantity"),
                "closed_quantity": exact["closed_quantity"],
                "gross_pnl": exact["gross_pnl"],
                "fees": exact["fees"],
                "net_pnl": exact["net_pnl"],
                "outcome": outcome,
                "exit_reason": exit_reason,
                "exit_price_source": exact["exit_price_source"],
                "opened_at": state.get("opened_at"),
                "closed_at": closed_at.isoformat(timespec="milliseconds"),
                "duration_seconds": duration,
                "metadata": {
                    "exact_binance_data": source == "binance_user_trades",
                    "exact_data_error": exact_error,
                    "closing_order_ids": exact.get("closing_order_ids", []),
                    "closing_trade_ids": exact.get("closing_trade_ids", []),
                    "closing_fills": exact.get("closing_fills", []),
                    "commission_assets": exact.get("commission_assets", []),
                    "income_audit": exact.get("income_audit", []),
                    "last_position_state": state,
                },
            })
            close_position_state(
                symbol=state["symbol"],
                side=state["side"],
                entry_price=entry,
                metadata={
                    "closed_by": "position_lifecycle_v25",
                    "completed_trade_id": trade["trade_id"],
                    "exit_reason": exit_reason,
                    "exact_binance_data": source == "binance_user_trades",
                },
            )
            record_event(
                "POSITION_CLOSED_EXACT",
                trade,
                symbol=state["symbol"],
                position_key=state["position_key"],
            )
            completed.append(trade)
        except Exception as error:
            errors.append(f'{state.get("symbol", "UNKNOWN")}: {error}')

    return {
        "status": "success" if not errors else "partial",
        "version": "v25",
        "closed_positions_detected": len(completed),
        "completed_trades": completed,
        "errors": errors,
    }