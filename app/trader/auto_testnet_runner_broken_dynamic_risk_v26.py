"""
TitanAI Auto Testnet Runner v25

Execution pipeline:
Portfolio Scanner
→ Ranked Candidate Fallback Selection
→ Legacy Confidence
→ Trade Quality Gate
→ Confirmation Engine
→ Risk Engine v2
→ Trade Builder
→ Existing Position Guard
→ Binance Futures Testnet Executor
→ Filled-Entry Verification
→ SL/TP Manager
→ Protection Verification
→ Exact Binance Fill Reconciliation
→ Position Lifecycle Journal
→ Daily Risk Manager
→ Performance Analytics
→ Trade Journal + AI Memory

Safety rules:
- Raw decision must be BUY or SELL
- Trade validation must pass
- Trade Quality Gate must pass
- Confirmation Engine must APPROVE
- Risk Engine must approve execution
- Trade Builder must produce a valid non-zero quantity
- Existing-position and concurrent-position guards must pass
- execute_trade must explicitly be True
- Entry must be verified as fully filled before SL/TP creation
- A completed execution is successful only when SL/TP is verified
"""

from typing import Any
import threading
import uuid
from datetime import datetime, timezone

from app.ai.confidence_engine import calculate_confidence
from app.ai.confirmation_engine import (
    evaluate_trade_confirmation,
)
from app.ai.trade_quality_gate import evaluate_trade_quality
from app.trader.trade_validator import validate_trade

from app.exchange.binance_testnet_client import (
    get_open_positions,
)

from app.memory.memory_engine import save_memory_record
from app.risk.risk_engine import calculate_risk_plan
from app.strategy.strategy_store import get_strategy

from app.trader.portfolio_scanner import scan_portfolio
from app.trader.break_even_manager import (
    manage_break_even_for_open_positions,
)
from app.trader.position_manager import manage_open_positions
from app.trader.partial_take_profit_manager import (
    manage_partial_take_profit_for_open_positions,
)
from app.trader.trailing_stop_manager import (
    manage_trailing_stop_for_open_positions,
)
from app.trader.sl_tp_manager import (
    inspect_position_protection,
    protect_verified_execution,
)
from app.trader.testnet_executor import execute_testnet_trade
from app.trader.trade_builder import build_trade_plan
from app.trader.trade_journal import save_cycle_result
from app.trader.persistent_trade_state import sync_cycle_state
from app.trader.position_lifecycle import reconcile_closed_positions
from app.trader.daily_risk_manager import evaluate_daily_risk
from app.trader.performance_analytics import build_performance_snapshot
from app.risk.account_protection import evaluate_account_protection
from app.risk.dynamic_position_sizer import (
    calculate_dynamic_position_size,
)
from app.risk.portfolio_exposure_manager import (
    evaluate_portfolio_exposure,
)
from app.services.exchange_info import (
    get_symbol_filters,
)


DEFAULT_STRATEGY = {
    "tp": 1.0,
    "sl": 1.0,
    "trailing": 0.3,
    "hold": 40,
    "win_rate": 50.0,
    "total_pnl": 0.0,
}

DEFAULT_BALANCE = 30.0
DEFAULT_RISK_PERCENT = 1.0
DEFAULT_LEVERAGE = 5.0

DEFAULT_MINIMUM_RISK_REWARD = 1.0
DEFAULT_MAXIMUM_RISK_PERCENT = 2.0
DEFAULT_MAXIMUM_LEVERAGE = 5.0
DEFAULT_MAXIMUM_POSITION_PERCENT = 25.0

DEFAULT_MAXIMUM_DAILY_LOSS_PERCENT = 3.0
DEFAULT_MAXIMUM_CONCURRENT_POSITIONS = 1

DEFAULT_BREAK_EVEN_TRIGGER_PERCENT = 0.50
DEFAULT_BREAK_EVEN_BUFFER_PERCENT = 0.10

DEFAULT_TRAILING_ACTIVATION_PERCENT = 0.75
DEFAULT_TRAILING_DISTANCE_PERCENT = 0.30
DEFAULT_TRAILING_MINIMUM_MOVE_PERCENT = 0.10

DEFAULT_PARTIAL_TP_STAGES = (
    {"name": "TP1", "trigger_percent": 0.50, "close_fraction": 0.25},
    {"name": "TP2", "trigger_percent": 1.00, "close_fraction": 0.25},
    {"name": "TP3", "trigger_percent": 1.50, "close_fraction": 0.25},
)
DEFAULT_PARTIAL_TP_RUNNER_FRACTION = 0.25

# Prevent overlapping scheduler/API cycles from submitting duplicate entries.
_CYCLE_LOCK = threading.Lock()


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)

        if result != result:
            return default

        if result in [
            float("inf"),
            float("-inf"),
        ]:
            return default

        return result

    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _get_strategy(symbol: str) -> dict:
    stored_strategy = get_strategy(symbol) or {}

    strategy = {
        **DEFAULT_STRATEGY,
        **stored_strategy,
    }

    strategy["tp"] = max(
        0.01,
        _safe_float(
            strategy.get("tp"),
            DEFAULT_STRATEGY["tp"],
        ),
    )

    strategy["sl"] = max(
        0.01,
        _safe_float(
            strategy.get("sl"),
            DEFAULT_STRATEGY["sl"],
        ),
    )

    strategy["trailing"] = max(
        0.0,
        _safe_float(
            strategy.get("trailing"),
            DEFAULT_STRATEGY["trailing"],
        ),
    )

    strategy["hold"] = max(
        1,
        _safe_int(
            strategy.get("hold"),
            DEFAULT_STRATEGY["hold"],
        ),
    )

    return strategy


def _position_is_open(position: Any) -> bool:
    """
    Return True only when a position has a non-zero amount.

    Binance may return rows for every symbol, including positions whose
    positionAmt is zero. Counting those rows as open positions can cause the
    Risk Engine concurrent-position guard to block every trade.
    """
    if not isinstance(position, dict):
        return False

    amount_keys = (
        "positionAmt",
        "position_amount",
        "positionAmount",
        "amount",
        "size",
        "qty",
        "quantity",
    )

    for key in amount_keys:
        if key in position:
            return abs(
                _safe_float(position.get(key), 0.0)
            ) > 0.0

    notional_keys = (
        "notional",
        "notionalValue",
        "initialMargin",
        "positionInitialMargin",
    )

    for key in notional_keys:
        if key in position:
            return abs(
                _safe_float(position.get(key), 0.0)
            ) > 0.0

    # Unknown position shape: do not silently treat it as an active position.
    return False


def _get_open_position_data() -> tuple[list, str | None, int]:
    try:
        positions = get_open_positions()

        if not isinstance(positions, list):
            return [], (
                "Open-position response was not a list"
            ), 0

        active_positions = [
            position
            for position in positions
            if _position_is_open(position)
        ]

        return active_positions, None, len(positions)

    except Exception as error:
        return [], str(error), 0


def _normalize_confirmation(
    confirmation: dict | None,
) -> dict:
    """
    Normalize Confirmation Engine key names for backward compatibility.
    """
    normalized = dict(confirmation or {})

    if "passed" not in normalized:
        normalized["passed"] = bool(
            normalized.get("approved", False)
        )

    if "approved" not in normalized:
        normalized["approved"] = bool(
            normalized.get("passed", False)
        )

    if "confirmation_score" not in normalized:
        normalized["confirmation_score"] = _safe_float(
            normalized.get("score"),
            0.0,
        )

    if "score" not in normalized:
        normalized["score"] = _safe_float(
            normalized.get("confirmation_score"),
            0.0,
        )

    normalized["decision"] = str(
        normalized.get("decision", "UNKNOWN")
    ).upper()

    return normalized



def _extract_directional_value(
    value: Any,
    keys: tuple[str, ...],
) -> Any:
    """Extract the first useful directional value from a nested result."""
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if candidate is not None and candidate != "":
                return candidate
        return None

    if isinstance(value, list):
        for item in value:
            candidate = _extract_directional_value(item, keys)
            if candidate is not None:
                return candidate
        return None

    return value


def _build_validator_inputs(
    best_setup: dict,
    final_decision: dict,
    ai_score: dict,
    confirmation: dict,
) -> tuple[dict, dict, dict]:
    """
    Enrich the existing validator inputs with independent confirmation data.

    The public validate_trade(...) signature remains unchanged. Additional
    evidence is placed into the dictionaries already accepted by Validator v3.
    """
    enriched_final_decision = dict(final_decision or {})
    enriched_ai_score = dict(ai_score or {})
    enriched_technical = dict(best_setup.get("technical") or {})

    confirmation_score = _safe_float(
        confirmation.get(
            "confirmation_score",
            confirmation.get("score"),
        ),
        0.0,
    )
    enriched_final_decision["confirmation_score"] = confirmation_score
    enriched_ai_score["confirmation_score"] = confirmation_score

    market_structure = _extract_directional_value(
        best_setup.get("market_structure"),
        (
            "signal",
            "trend",
            "direction",
            "structure",
            "market_structure",
            "bias",
        ),
    )
    if market_structure is not None:
        enriched_technical["market_structure"] = market_structure

    vwap_direction = _extract_directional_value(
        best_setup.get("vwap"),
        (
            "bias",
            "signal",
            "direction",
            "position",
            "trend",
        ),
    )
    if vwap_direction is not None:
        enriched_technical["vwap_position"] = vwap_direction

    whale_direction = _extract_directional_value(
        best_setup.get("whale_activity"),
        (
            "state",
            "signal",
            "direction",
            "activity",
            "bias",
        ),
    )
    if whale_direction is not None:
        enriched_final_decision["whale_activity"] = whale_direction
        enriched_ai_score["whale_activity"] = whale_direction

    liquidity_direction = _extract_directional_value(
        best_setup.get("liquidity_trend"),
        (
            "signal",
            "direction",
            "pressure",
            "latest_pressure",
            "trend",
            "bias",
        ),
    )
    if liquidity_direction is not None:
        enriched_final_decision["liquidity"] = liquidity_direction
        enriched_ai_score["liquidity"] = liquidity_direction

    fvg_direction = _extract_directional_value(
        best_setup.get("fair_value_gaps"),
        (
            "signal",
            "direction",
            "bias",
            "type",
            "state",
        ),
    )
    if fvg_direction is not None:
        enriched_technical["fvg_signal"] = fvg_direction

    return (
        enriched_final_decision,
        enriched_ai_score,
        enriched_technical,
    )


def _extract_confidence_score(
    confidence: dict | None,
    ai_score: dict | None,
) -> float:
    confidence = confidence or {}
    ai_score = ai_score or {}

    for key in (
        "adjusted_confidence_score",
        "directional_confidence_score",
        "final_confidence",
        "confidence",
        "confidence_score",
        "score",
    ):
        if key in confidence:
            return max(
                0.0,
                min(
                    100.0,
                    _safe_float(confidence.get(key), 0.0),
                ),
            )

    for key in (
        "self_learning_calibrated_score",
        "institutional_directional_score",
        "directional_score",
        "score",
    ):
        if key in ai_score:
            return max(
                0.0,
                min(
                    100.0,
                    _safe_float(ai_score.get(key), 0.0),
                ),
            )

    return 0.0


def _extract_volatility_percent(candidate: dict) -> float:
    sources = (
        candidate,
        candidate.get("technical") or {},
        candidate.get("volatility") or {},
        candidate.get("market_regime") or {},
        candidate.get("live_market_regime") or {},
    )

    for source in sources:
        if not isinstance(source, dict):
            continue

        for key in (
            "volatility_percent",
            "atr_percent",
            "atr_pct",
            "normalized_atr_percent",
            "range_percent",
        ):
            value = _safe_float(source.get(key), 0.0)
            if value > 0:
                return value

    return 1.0


async def _evaluate_candidate_for_selection(
    candidate: dict,
    *,
    quantity: float | None,
    balance: float,
    risk_percent: float,
    leverage: float,
    current_daily_pnl: float,
    open_positions_count: int,
    open_positions: list[dict] | None = None,
) -> dict:
    """
    Evaluate one scanner-ranked candidate through all pre-execution safety gates.

    This function has no order-submission side effects. It allows the runner to
    skip a high-ranked candidate that becomes non-executable after Trade Quality
    sizing (for example, SMALL_TRADE falling below Binance min notional) and try
    the next execution-eligible candidate.
    """
    symbol = str(candidate.get("symbol", "")).upper()
    price = _safe_float(candidate.get("price"), 0.0)
    ai_score = candidate.get("ai_score", {}) or {}
    final_decision = candidate.get("final_decision", {}) or {}
    initial_validation = candidate.get("validation", {}) or {}

    optimized_strategy = _get_strategy(symbol)

    confidence = calculate_confidence(
        symbol,
        ai_score,
    )

    confirmation = evaluate_trade_confirmation(
        ai_score=ai_score,
        order_flow=candidate.get("order_flow"),
        liquidity_trend=candidate.get("liquidity_trend"),
        liquidity_sweep=candidate.get("liquidity_sweep"),
        absorption=candidate.get("absorption"),
        iceberg=candidate.get("iceberg"),
        whale_activity=candidate.get("whale_activity"),
        market_structure=candidate.get("market_structure"),
        volume_profile=candidate.get("volume_profile"),
        vwap=candidate.get("vwap"),
        fair_value_gaps=candidate.get("fair_value_gaps"),
        technical=candidate.get("technical"),
        multi_timeframe=candidate.get("multi_timeframe"),
    )
    confirmation = _normalize_confirmation(confirmation)

    (
        validator_final_decision,
        validator_ai_score,
        validator_technical,
    ) = _build_validator_inputs(
        best_setup=candidate,
        final_decision=final_decision,
        ai_score=ai_score,
        confirmation=confirmation,
    )

    validation = validate_trade(
        final_decision=validator_final_decision,
        ai_score=validator_ai_score,
        order_book=candidate.get("order_book", {}),
        technical=validator_technical,
        multi_timeframe=candidate.get("multi_timeframe", {}),
    )
    validation["initial_scanner_validation"] = initial_validation

    trade_quality = evaluate_trade_quality(
        order_book=candidate.get("order_book", {}),
        order_flow=candidate.get("order_flow", {}),
        liquidity_trend=candidate.get("liquidity_trend"),
        confidence=confidence,
        validation=validation,
        direction=final_decision.get("decision", "HOLD"),
    )

    confidence_score = _extract_confidence_score(
        confidence,
        ai_score,
    )
    volatility_percent = _extract_volatility_percent(
        candidate
    )

    dynamic_sizing = calculate_dynamic_position_size(
        balance=balance,
        base_risk_percent=risk_percent,
        stop_loss_percent=optimized_strategy["sl"],
        confidence_score=confidence_score,
        volatility_percent=volatility_percent,
        requested_leverage=leverage,
        maximum_leverage=DEFAULT_MAXIMUM_LEVERAGE,
        maximum_position_percent=(
            DEFAULT_MAXIMUM_POSITION_PERCENT
        ),
        minimum_position_usdt=0.0,
    )

    dynamic_position_usdt = _safe_float(
        dynamic_sizing.get(
            "recommended_position_usdt"
        ),
        0.0,
    )
    dynamic_risk_percent = _safe_float(
        dynamic_sizing.get(
            "effective_risk_percent"
        ),
        risk_percent,
    )
    dynamic_leverage = _safe_float(
        dynamic_sizing.get(
            "recommended_leverage"
        ),
        leverage,
    )
    dynamic_position_percent = (
        dynamic_position_usdt
        / balance
        * 100.0
        if balance > 0
        else 0.0
    )

    portfolio_exposure = evaluate_portfolio_exposure(
        balance=balance,
        proposed_symbol=symbol,
        proposed_side=str(
            final_decision.get(
                "decision",
                "HOLD",
            )
        ).upper(),
        proposed_position_usdt=dynamic_position_usdt,
        open_positions=open_positions or [],
        maximum_total_exposure_percent=(
            DEFAULT_MAXIMUM_POSITION_PERCENT
        ),
        maximum_concurrent_positions=(
            DEFAULT_MAXIMUM_CONCURRENT_POSITIONS
        ),
        block_correlated_same_direction=True,
    )

    # Reuse the exact bounded risk decision selected above.
    risk_plan = dict(
        selected_evaluation.get(
            "risk_plan",
            {},
        )
    )
    dynamic_sizing = dict(
        selected_evaluation.get(
            "dynamic_sizing",
            {},
        )
    )
    portfolio_exposure = dict(
        selected_evaluation.get(
            "portfolio_exposure",
            {},
        )
    )

    selected_exchange_filters = selected_evaluation.get(
        "exchange_filters",
        {},
    )
    selected_exchange_filters_error = selected_evaluation.get(
        "exchange_filters_error"
    )

    trade_plan = build_trade_plan(
        symbol=symbol,
        price=price,
        final_decision=final_decision,
        confirmation=confirmation,
        risk_plan=risk_plan,
        quantity=quantity,
        exchange_filters=(
            selected_exchange_filters
            if not selected_exchange_filters_error
            else None
        ),
    )

    exchange_filters = {"symbol": symbol,"min_notional":0.0,"min_qty":0.0,"step_size":0.0,"tick_size":0.0,"status":"error"}
    exchange_filters_error = None
    try:
        fetched_filters = await get_symbol_filters(symbol)
        if not isinstance(fetched_filters, dict):
            raise RuntimeError("Exchange filter service returned a non-dictionary response")
        exchange_filters = {**exchange_filters, **fetched_filters, "symbol": symbol, "status":"ready"}
    except Exception as error:
        exchange_filters_error = str(error)

    requested_position_usdt = _safe_float(trade_plan.get("position_size_usdt"),0.0)
    required_margin_usdt = _safe_float(trade_plan.get("margin_required"),0.0)
    exchange_minimum_notional = _safe_float(exchange_filters.get("min_notional"),0.0)

    if exchange_filters_error:
        account_protection = {
            "allowed":False,
            "status":"blocked",
            "reason":"Exchange filters could not be verified; execution is blocked for safety",
            "error":exchange_filters_error,
            "requested_position_usdt":requested_position_usdt,
            "required_margin_usdt":required_margin_usdt,
            "exchange_minimum_notional":exchange_minimum_notional,
        }
    else:
        account_protection = evaluate_account_protection(
            balance=balance,
            available_balance=balance,
            requested_position_usdt=requested_position_usdt,
            required_margin_usdt=required_margin_usdt,
            exchange_minimum_notional=exchange_minimum_notional,
        )

    execution_blocks = _collect_execution_blocks(
        execute_trade=execute_trade,
        final_decision=final_decision,
        validation=validation,
        confidence=confidence,
        trade_quality=trade_quality,
        confirmation=confirmation,
        risk_plan=risk_plan,
        trade_plan=trade_plan,
    )

    if position_query_error:
        execution_blocks.append(
            "Open positions could not be verified; execution is blocked for safety: "
            + str(position_query_error)
        )

    if account_protection.get("allowed") is not True:
        execution_blocks.append(
            "Account Protection: "
            + str(
                account_protection.get(
                    "reason",
                    "Account protection did not approve execution",
                )
            )
        )

    execution_blocks = list(dict.fromkeys(execution_blocks))

    base_result = {
        "status": "success",
        "position_lifecycle": lifecycle,
        "daily_risk": daily_risk,
        "performance_analytics": performance_analytics,
        "scan": scan,
        "candidate_attempts": candidate_attempts,
        "candidates_evaluated": len(candidate_attempts),
        "selected_candidate_rank": scan.get("selected_candidate_rank"),
        "symbol": symbol,
        "price": price,
        "exchange_filters": exchange_filters,
        "exchange_filters_error": exchange_filters_error,
        "account_protection": account_protection,

        "scan_summary": {
            "total_symbols": scan.get(
                "total_symbols",
                0,
            ),
            "best_symbol": symbol,
            "ranked_count": len(
                scan.get("ranked", [])
            ),
            "valid_ranked_count": len(
                scan.get("valid_ranked", [])
            ),
            "error_count": len(
                scan.get("errors", [])
            ),
        },

        "best_setup": best_setup,
        "ai_score": ai_score,
        "final_decision": final_decision,

        "optimized_strategy": (
            optimized_strategy
        ),

        "confidence": confidence,
        "trade_quality": trade_quality,
        "confirmation": confirmation,
        "validation": validation,

        "risk_plan": risk_plan,
        "dynamic_sizing": dynamic_sizing,
        "portfolio_exposure": portfolio_exposure,
        "trade_plan": trade_plan,

        "position_size_usdt": (
            risk_plan.get(
                "position_size_usdt",
                0.0,
            )
        ),
        "quantity": trade_plan.get(
            "quantity",
            0.0,
        ),
        "quantity_error": trade_plan.get(
            "quantity_error",
        ),

        "open_positions_count": (
            open_positions_count
        ),
        "raw_open_positions_count": (
            raw_open_positions_count
        ),
        "open_positions": open_positions,
        "position_query_error": (
            position_query_error
        ),
        "position_manager": position_status,
        "partial_take_profit_manager": {
            "results": partial_take_profit_results,
            "error": partial_take_profit_error,
        },
        "break_even_manager": {
            "results": break_even_results,
            "error": break_even_error,
        },
        "trailing_stop_manager": {
            "results": trailing_stop_results,
            "error": trailing_stop_error,
        },
        "protection_inspection": {
            "results": protection_results,
            "errors": protection_inspection_errors,
        },
        "persistent_trade_state": persistent_state,

        "execute_trade_requested": (
            execute_trade
        ),
        "execution_blocks": execution_blocks,
    }

    if position_query_error:
        base_result.setdefault(
            "warnings",
            [],
        ).append(
            "Could not verify all open positions: "
            f"{position_query_error}"
        )

    if position_status.get("status") not in {"no_position", "error"}:
        result = {
            **base_result,
            "execution": {
                "status": "skipped",
                "reason": (
                    "Existing position managed"
                ),
                "position_status": (
                    position_status.get("status")
                ),
                "partial_take_profit_manager": {
                    "results": partial_take_profit_results,
                    "error": partial_take_profit_error,
                },
                "break_even_manager": {
                    "results": break_even_results,
                    "error": break_even_error,
                },
                "trailing_stop_manager": {
                    "results": trailing_stop_results,
                    "error": trailing_stop_error,
                },
            },
        }

        save_result(result)
        return result

    if position_status.get("status") == "error":
        execution_blocks.append(
            "Position Manager could not safely determine position state: "
            + str(position_status.get("reason", "unknown error"))
        )
        execution_blocks = list(dict.fromkeys(execution_blocks))
        base_result["execution_blocks"] = execution_blocks

    can_execute = execute_trade and not execution_blocks

    if not execute_trade:
        execution = {
            "status": "skipped",
            "reason": (
                "execute_trade flag is false"
            ),
            "mode": "ANALYSIS_ONLY",
            "decision": final_decision.get(
                "decision",
                "HOLD",
            ),
            "trade_plan_ready": (
                trade_plan.get("ready", False)
            ),
        }

    elif not can_execute:
        execution = {
            "status": "blocked",
            "reason": (
                "Execution blocked by safety gates"
            ),
            "mode": "SAFETY_LOCKED",
            "decision": final_decision.get(
                "decision",
                "HOLD",
            ),
            "block_reasons": execution_blocks,
        }

    else:
        execution = _execute_verify_and_protect(
            final_decision=final_decision,
            symbol=symbol,
            trade_plan=trade_plan,
        )

    result = {
        **base_result,
        "execution": execution,
    }

    if str(execution.get("status", "")).lower() in {
        "protected", "unsafe", "verified_filled", "filled"
    }:
        try:
            refreshed_positions, refresh_error, _ = _get_open_position_data()
            refreshed_protection, refreshed_protection_errors = (
                _inspect_open_position_protection(refreshed_positions)
            )
            refreshed_state = sync_cycle_state(
                open_positions=refreshed_positions,
                partial_take_profit_results=partial_take_profit_results,
                break_even_results=break_even_results,
                trailing_stop_results=trailing_stop_results,
                protection_results=refreshed_protection,
            )
            if refresh_error:
                refreshed_state.setdefault("errors", []).append(refresh_error)
            refreshed_state.setdefault("errors", []).extend(
                refreshed_protection_errors
            )
            result["persistent_trade_state"] = refreshed_state
            result["protection_inspection"] = {
                "results": refreshed_protection,
                "errors": refreshed_protection_errors,
            }
        except Exception as error:
            result.setdefault("warnings", []).append(
                f"Post-execution state refresh failed: {error}"
            )

    save_result(result)

    return result

async def run_auto_testnet_cycle(
    quantity: float | None = None,
    execute_trade: bool = False,
    balance: float = DEFAULT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    leverage: float = DEFAULT_LEVERAGE,
    current_daily_pnl: float = 0.0,
    scan_limit: int = 20,
) -> dict:
    """Run one non-overlapping TitanAI testnet cycle.

    The process-wide lock is intentionally non-blocking. A scheduler overlap is
    skipped instead of waiting and later submitting a stale duplicate trade.
    """
    cycle_id = uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()

    if not _CYCLE_LOCK.acquire(blocking=False):
        result = {
            "status": "skipped",
            "reason": "Another auto-testnet cycle is already running",
            "cycle_id": cycle_id,
            "started_at": started_at,
            "execution": {
                "status": "skipped",
                "mode": "CONCURRENCY_GUARD",
                "reason": "Overlapping cycle blocked to prevent duplicate execution",
            },
        }
        save_result(result)
        return result

    try:
        result = await _run_auto_testnet_cycle_unlocked(
            quantity=quantity,
            execute_trade=execute_trade,
            balance=balance,
            risk_percent=risk_percent,
            leverage=leverage,
            current_daily_pnl=current_daily_pnl,
            scan_limit=scan_limit,
        )
        if not isinstance(result, dict):
            result = {
                "status": "error",
                "reason": "Auto Testnet Runner returned a non-dictionary result",
                "raw_result": result,
                "execution": {
                    "status": "error",
                    "mode": "SAFETY_LOCKED",
                },
            }
        result.setdefault("cycle_id", cycle_id)
        result.setdefault("started_at", started_at)
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        return result
    except Exception as error:
        result = {
            "status": "error",
            "reason": "Unhandled Auto Testnet Runner exception",
            "error": str(error),
            "cycle_id": cycle_id,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "execution": {
                "status": "error",
                "mode": "SAFETY_LOCKED",
                "reason": "Execution stopped by the top-level safety boundary",
            },
        }
        save_result(result)
        return result
    finally:
        _CYCLE_LOCK.release()