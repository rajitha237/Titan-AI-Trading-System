"""
TitanAI Portfolio Scanner v2

Dynamic Binance Futures scanner using Market Snapshot architecture.

Adds execution-aware ranking:
- Fetches Binance Futures symbol filters
- Rejects symbols whose exchange minimum notional exceeds the configured
  maximum position exposure
- Keeps analysis results for audit, while selecting only executable,
  validated setups as best_setup
"""

from typing import Any

from app.universe.dynamic_universe import (
    get_dynamic_trade_universe,
)
from app.services.market_snapshot import (
    get_market_snapshot,
)
from app.services.exchange_info import (
    get_symbol_filters,
)

from app.ai.technical_engine import analyze_technical
from app.ai.multi_timeframe_engine import (
    analyze_multi_timeframe,
)
from app.ai.scoring_engine import calculate_ai_score
from app.ai.strategy_engine import make_trade_decision

from app.trader.trade_validator import validate_trade


DEFAULT_MAXIMUM_POSITION_USDT = 7.5


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


def _build_execution_eligibility(
    symbol: str,
    price: float,
    maximum_position_usdt: float,
    exchange_filters: dict,
    exchange_filters_error: str | None,
) -> dict:
    """
    Determine whether a symbol can be traded without exceeding the configured
    maximum position exposure.

    This is an early scanner-level eligibility check. Final account, risk,
    quantity, and exchange checks remain enforced by the Auto Testnet Runner.
    """
    maximum_position_usdt = max(
        0.0,
        _safe_float(maximum_position_usdt, 0.0),
    )

    if exchange_filters_error:
        return {
            "allowed": False,
            "status": "blocked",
            "symbol": symbol,
            "reason": (
                "Exchange filters could not be verified"
            ),
            "maximum_position_usdt": maximum_position_usdt,
            "exchange_minimum_notional": 0.0,
            "estimated_minimum_quantity": 0.0,
            "error": exchange_filters_error,
        }

    minimum_notional = max(
        0.0,
        _safe_float(
            exchange_filters.get("min_notional"),
            0.0,
        ),
    )

    minimum_quantity = max(
        0.0,
        _safe_float(
            exchange_filters.get("min_qty"),
            0.0,
        ),
    )

    estimated_minimum_quantity = 0.0

    if price > 0 and minimum_notional > 0:
        estimated_minimum_quantity = (
            minimum_notional / price
        )

    block_reasons: list[str] = []

    if maximum_position_usdt <= 0:
        block_reasons.append(
            "Maximum position exposure is zero or invalid"
        )

    if minimum_notional <= 0:
        block_reasons.append(
            "Exchange minimum notional is zero or unavailable"
        )

    if (
        minimum_notional > 0
        and maximum_position_usdt > 0
        and minimum_notional > maximum_position_usdt
    ):
        block_reasons.append(
            "Exchange minimum notional exceeds the configured "
            "maximum position exposure"
        )

    allowed = not block_reasons

    return {
        "allowed": allowed,
        "status": "eligible" if allowed else "blocked",
        "symbol": symbol,
        "reason": (
            "Symbol is executable within the configured exposure"
            if allowed
            else block_reasons[0]
        ),
        "maximum_position_usdt": maximum_position_usdt,
        "exchange_minimum_notional": minimum_notional,
        "exchange_minimum_quantity": minimum_quantity,
        "estimated_minimum_quantity": (
            estimated_minimum_quantity
        ),
        "block_reasons": block_reasons,
    }


async def analyze_symbol(
    symbol: str,
    maximum_position_usdt: float = (
        DEFAULT_MAXIMUM_POSITION_USDT
    ),
) -> dict:
    snapshot = await get_market_snapshot(symbol)

    price = _safe_float(snapshot["price"], 0.0)
    candles = snapshot["candles"]

    order_book = snapshot["order_book"]
    order_flow = snapshot["order_flow"]

    liquidity = snapshot.get("liquidity")
    liquidity_trend = snapshot.get(
        "liquidity_trend"
    )
    liquidity_sweep = snapshot.get(
        "liquidity_sweep"
    )

    absorption = snapshot.get("absorption")
    iceberg = snapshot.get("iceberg")

    whale_activity = snapshot.get(
        "whale_activity"
    )
    market_structure = snapshot.get(
        "market_structure"
    )

    volume_profile = snapshot.get(
        "volume_profile"
    )
    vwap = snapshot.get("vwap")
    fair_value_gaps = snapshot.get(
        "fair_value_gaps"
    )

    open_interest = snapshot["open_interest"]
    funding_rate = snapshot["funding_rate"]

    technical = analyze_technical(candles)

    multi_timeframe = await analyze_multi_timeframe(
        symbol
    )

    ai_score = calculate_ai_score(
        order_book=order_book,
        order_flow=order_flow,
        liquidity_trend=liquidity_trend,
        liquidity_sweep=liquidity_sweep,
        absorption=absorption,
        iceberg=iceberg,
        whale_activity=whale_activity,
        market_structure=market_structure,
        volume_profile=volume_profile,
        vwap=vwap,
        fair_value_gaps=fair_value_gaps,
        open_interest=open_interest,
        funding_rate=funding_rate,
        technical=technical,
        multi_timeframe=multi_timeframe,
    )

    final_decision = make_trade_decision(ai_score)

    validation = validate_trade(
        final_decision,
        ai_score,
        order_book,
        technical,
        multi_timeframe,
    )

    exchange_filters = {
        "symbol": symbol,
        "min_notional": 0.0,
        "min_qty": 0.0,
        "step_size": 0.0,
        "tick_size": 0.0,
        "status": "error",
    }
    exchange_filters_error = None

    try:
        fetched_filters = await get_symbol_filters(
            symbol
        )

        if not isinstance(fetched_filters, dict):
            raise RuntimeError(
                "Exchange filter service returned a "
                "non-dictionary response"
            )

        exchange_filters = {
            **exchange_filters,
            **fetched_filters,
            "symbol": symbol,
            "status": "ready",
        }

    except Exception as error:
        exchange_filters_error = str(error)

    execution_eligibility = (
        _build_execution_eligibility(
            symbol=symbol,
            price=price,
            maximum_position_usdt=(
                maximum_position_usdt
            ),
            exchange_filters=exchange_filters,
            exchange_filters_error=(
                exchange_filters_error
            ),
        )
    )

    return {
        "symbol": symbol,
        "price": price,

        "snapshot": {
            "price": price,
            "order_book": order_book,
            "order_flow": order_flow,
            "liquidity": liquidity,
            "liquidity_trend": liquidity_trend,
            "liquidity_sweep": liquidity_sweep,
            "absorption": absorption,
            "iceberg": iceberg,
            "whale_activity": whale_activity,
            "market_structure": market_structure,
            "volume_profile": volume_profile,
            "vwap": vwap,
            "fair_value_gaps": fair_value_gaps,
            "open_interest": open_interest,
            "funding_rate": funding_rate,
        },

        "order_book": order_book,
        "order_flow": order_flow,
        "liquidity": liquidity,
        "liquidity_trend": liquidity_trend,
        "liquidity_sweep": liquidity_sweep,
        "absorption": absorption,
        "iceberg": iceberg,
        "whale_activity": whale_activity,
        "market_structure": market_structure,
        "volume_profile": volume_profile,
        "vwap": vwap,
        "fair_value_gaps": fair_value_gaps,
        "technical": technical,
        "multi_timeframe": multi_timeframe,
        "ai_score": ai_score,
        "final_decision": final_decision,
        "validation": validation,

        "exchange_filters": exchange_filters,
        "exchange_filters_error": (
            exchange_filters_error
        ),
        "execution_eligibility": (
            execution_eligibility
        ),
        "executable": (
            execution_eligibility.get("allowed")
            is True
        ),
    }


async def scan_portfolio(
    limit: int = 20,
    maximum_position_usdt: float = (
        DEFAULT_MAXIMUM_POSITION_USDT
    ),
) -> dict:
    maximum_position_usdt = max(
        0.0,
        _safe_float(
            maximum_position_usdt,
            DEFAULT_MAXIMUM_POSITION_USDT,
        ),
    )

    symbols = await get_dynamic_trade_universe(
        limit=limit
    )

    results = []

    for symbol in symbols:
        try:
            result = await analyze_symbol(
                symbol=symbol,
                maximum_position_usdt=(
                    maximum_position_usdt
                ),
            )
            results.append(result)

        except Exception as error:
            results.append({
                "symbol": symbol,
                "error": str(error),
            })

    ranked = sorted(
        [
            item
            for item in results
            if "ai_score" in item
        ],
        key=lambda item: _safe_float(
            item.get("ai_score", {}).get("score"),
            0.0,
        ),
        reverse=True,
    )

    validated_ranked = [
        item
        for item in ranked
        if item.get(
            "validation",
            {},
        ).get("allowed") is True
    ]

    executable_ranked = [
        item
        for item in ranked
        if item.get(
            "execution_eligibility",
            {},
        ).get("allowed") is True
    ]

    valid_ranked = [
        item
        for item in validated_ranked
        if item.get(
            "execution_eligibility",
            {},
        ).get("allowed") is True
    ]

    # Never fall back to a non-executable or validation-blocked symbol.
    best_setup = (
        valid_ranked[0]
        if valid_ranked
        else None
    )

    ineligible = [
        {
            "symbol": item.get("symbol"),
            "ai_score": item.get(
                "ai_score",
                {},
            ).get("score"),
            "validation_allowed": item.get(
                "validation",
                {},
            ).get("allowed"),
            "reason": item.get(
                "execution_eligibility",
                {},
            ).get("reason"),
            "maximum_position_usdt": item.get(
                "execution_eligibility",
                {},
            ).get("maximum_position_usdt"),
            "exchange_minimum_notional": item.get(
                "execution_eligibility",
                {},
            ).get("exchange_minimum_notional"),
        }
        for item in ranked
        if item.get(
            "execution_eligibility",
            {},
        ).get("allowed") is not True
    ]

    return {
        "status": "success",
        "total_symbols": len(symbols),
        "symbols": symbols,
        "maximum_position_usdt": (
            maximum_position_usdt
        ),
        "best_setup": best_setup,
        "ranked": ranked,
        "validated_ranked": validated_ranked,
        "executable_ranked": executable_ranked,
        "valid_ranked": valid_ranked,
        "ineligible": ineligible,
        "executable_count": len(executable_ranked),
        "valid_executable_count": len(valid_ranked),
        "errors": [
            item
            for item in results
            if "error" in item
        ],
    }