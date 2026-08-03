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
    get_open_orders,
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
from app.trader.live_position_synchronizer import (
    synchronise_live_positions,
)
from app.trader.order_recovery_engine import (
    recover_open_orders,
)
from app.trader.execution_watchdog import (
    evaluate_execution_watchdog,
)
from app.service.service_state_manager import (
    begin_service_cycle,
    complete_service_cycle,
)
from app.dashboard.system_dashboard import (
    build_system_dashboard,
)
from app.notifications.notification_router import (
    route_notifications,
)
from app.config.startup_checks import (
    evaluate_startup_readiness,
)
from app.performance.performance_service import (
    build_and_store_performance,
)
from app.operations.operations_service import (
    build_operations_snapshot,
)
from app.operations.operations_backup_service import (
    build_backup_operations_snapshot,
)
from app.operations.production_report import (
    build_production_readiness_report,
)
from app.trader.trade_integrity_service import (
    build_trade_integrity_snapshot,
)
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


def _get_open_order_data() -> tuple[list, str | None]:
    try:
        orders = get_open_orders()

        if not isinstance(orders, list):
            return [], (
                "Open-order response was not a list"
            )

        return orders, None

    except Exception as error:
        return [], str(error)


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
                    _safe_float(
                        confidence.get(key),
                        0.0,
                    ),
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
                    _safe_float(
                        ai_score.get(key),
                        0.0,
                    ),
                ),
            )

    return 0.0


def _extract_volatility_percent(
    candidate: dict,
) -> float:
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
            value = _safe_float(
                source.get(key),
                0.0,
            )

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

    risk_plan = calculate_risk_plan(
        balance=balance,
        risk_percent=dynamic_risk_percent,
        leverage=dynamic_leverage,
        stop_loss_percent=optimized_strategy["sl"],
        take_profit_percent=optimized_strategy["tp"],
        confirmation=confirmation,
        require_confirmation=True,
        trade_quality_action=trade_quality.get("action", "REJECT"),
        current_daily_pnl=current_daily_pnl,
        open_positions_count=open_positions_count,
        minimum_risk_reward=DEFAULT_MINIMUM_RISK_REWARD,
        maximum_risk_percent=DEFAULT_MAXIMUM_RISK_PERCENT,
        maximum_leverage=DEFAULT_MAXIMUM_LEVERAGE,
        maximum_position_percent=max(
            1.0,
            min(
                DEFAULT_MAXIMUM_POSITION_PERCENT,
                dynamic_position_percent,
            ),
        ),
        maximum_daily_loss_percent=DEFAULT_MAXIMUM_DAILY_LOSS_PERCENT,
        maximum_concurrent_positions=DEFAULT_MAXIMUM_CONCURRENT_POSITIONS,
        mode="TESTNET",
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
        fetched_filters = await get_symbol_filters(symbol)
        if not isinstance(fetched_filters, dict):
            raise RuntimeError(
                "Exchange filter service returned a non-dictionary response"
            )
        exchange_filters = {
            **exchange_filters,
            **fetched_filters,
            "symbol": symbol,
            "status": "ready",
        }
    except Exception as error:
        exchange_filters_error = str(error)

    trade_plan = build_trade_plan(
        symbol=symbol,
        price=price,
        final_decision=final_decision,
        confirmation=confirmation,
        risk_plan=risk_plan,
        quantity=quantity,
        exchange_filters=(
            exchange_filters
            if exchange_filters_error is None
            else None
        ),
    )

    requested_position_usdt = _safe_float(
        trade_plan.get("position_size_usdt"),
        0.0,
    )
    required_margin_usdt = _safe_float(
        trade_plan.get("margin_required"),
        0.0,
    )
    exchange_minimum_notional = _safe_float(
        exchange_filters.get("min_notional"),
        0.0,
    )

    if exchange_filters_error:
        account_protection = {
            "allowed": False,
            "status": "blocked",
            "reason": (
                "Exchange filters could not be verified; "
                "execution is blocked for safety"
            ),
            "error": exchange_filters_error,
            "requested_position_usdt": requested_position_usdt,
            "dynamic_position_usdt": dynamic_position_usdt,
            "dynamic_risk_percent": dynamic_risk_percent,
            "volatility_percent": volatility_percent,
            "confidence_score": confidence_score,
            "portfolio_exposure_allowed": (
                portfolio_exposure.get("allowed")
            ),
            "required_margin_usdt": required_margin_usdt,
            "exchange_minimum_notional": exchange_minimum_notional,
        }
    else:
        account_protection = evaluate_account_protection(
            balance=balance,
            available_balance=balance,
            requested_position_usdt=requested_position_usdt,
            required_margin_usdt=required_margin_usdt,
            exchange_minimum_notional=exchange_minimum_notional,
        )

    blockers = _collect_execution_blocks(
        # Candidate selection evaluates execution readiness independently of
        # whether this cycle is analysis-only or has execute_trade=True.
        execute_trade=True,
        final_decision=final_decision,
        validation=validation,
        confidence=confidence,
        trade_quality=trade_quality,
        confirmation=confirmation,
        risk_plan=risk_plan,
        trade_plan=trade_plan,
    )

    if dynamic_sizing.get("executable") is not True:
        for reason in dynamic_sizing.get(
            "block_reasons",
            [],
        ):
            blockers.append(
                f"Dynamic Sizer: {reason}"
            )

    if portfolio_exposure.get("allowed") is not True:
        for reason in portfolio_exposure.get(
            "block_reasons",
            [],
        ):
            blockers.append(
                f"Portfolio Exposure: {reason}"
            )

    if account_protection.get("allowed") is not True:
        blockers.append(
            "Account Protection: "
            + str(
                account_protection.get(
                    "reason",
                    "Account protection did not approve execution",
                )
            )
        )

    blockers = list(dict.fromkeys(blockers))

    return {
        "symbol": symbol,
        "candidate": candidate,
        "accepted": not blockers,
        "block_reasons": blockers,
        "validation": validation,
        "confirmation": confirmation,
        "trade_quality": trade_quality,
        "confidence": confidence,
        "risk_plan": risk_plan,
        "trade_plan": trade_plan,
        "exchange_filters": exchange_filters,
        "exchange_filters_error": exchange_filters_error,
        "account_protection": account_protection,
        "dynamic_sizing": dynamic_sizing,
        "portfolio_exposure": portfolio_exposure,
        "summary": {
            "ai_score": _safe_float(ai_score.get("score"), 0.0),
            "decision": str(
                final_decision.get("decision", "HOLD")
            ).upper(),
            "trade_quality_action": str(
                trade_quality.get("action", "REJECT")
            ).upper(),
            "requested_position_usdt": requested_position_usdt,
            "exchange_minimum_notional": exchange_minimum_notional,
        },
    }


def _collect_execution_blocks(
    execute_trade: bool,
    final_decision: dict,
    validation: dict,
    confidence: dict,
    trade_quality: dict,
    confirmation: dict,
    risk_plan: dict,
    trade_plan: dict,
) -> list[str]:
    blocks = []

    decision = str(
        final_decision.get("decision", "HOLD")
    ).upper()

    if not execute_trade:
        blocks.append(
            "execute_trade flag is false"
        )

    if decision not in ["BUY", "SELL"]:
        blocks.append(
            f"Final decision is {decision}"
        )

    if validation.get("allowed") is not True:
        blocks.append(
            "Trade Validator did not allow the setup"
        )

        validation_reason = validation.get("reason")

        if validation_reason:
            blocks.append(
                f"Validation reason: {validation_reason}"
            )

    if trade_quality.get("passed") is not True:
        blocks.append(
            "Trade Quality Gate did not pass"
        )

    quality_action = str(
        trade_quality.get("action", "REJECT")
    ).upper()

    if quality_action not in [
        "TRADE",
        "SMALL_TRADE",
    ]:
        blocks.append(
            f"Trade Quality action is {quality_action}"
        )

    if confirmation.get("passed") is not True:
        blocks.append(
            "Confirmation Engine did not pass"
        )

    confirmation_decision = str(
        confirmation.get("decision", "UNKNOWN")
    ).upper()

    if confirmation_decision != "APPROVE":
        blocks.append(
            "Confirmation Engine decision is "
            f"{confirmation_decision}"
        )

    if confirmation.get("hard_blocks"):
        for hard_block in confirmation["hard_blocks"]:
            blocks.append(
                f"Confirmation block: {hard_block}"
            )

    if risk_plan.get("approved") is not True:
        blocks.append(
            "Risk Engine did not approve the trade"
        )

    if risk_plan.get("execution_allowed") is not True:
        blocks.append(
            "Risk Engine has execution disabled"
        )

    for risk_block in risk_plan.get(
        "block_reasons",
        [],
    ):
        blocks.append(
            f"Risk block: {risk_block}"
        )

    if trade_plan.get("ready") is not True:
        blocks.append(
            "Trade Builder did not produce a ready plan"
        )

    if trade_plan.get("execution_allowed") is not True:
        blocks.append(
            "Trade Builder has execution disabled"
        )

    for builder_block in trade_plan.get(
        "block_reasons",
        [],
    ):
        blocks.append(
            f"Trade Builder block: {builder_block}"
        )

    quantity = _safe_float(
        trade_plan.get("quantity"),
        0.0,
    )

    if quantity <= 0:
        blocks.append(
            "Trade quantity is zero or invalid"
        )

    confidence_decision = str(
        confidence.get("decision", "UNKNOWN")
    ).upper()

    if confidence_decision not in [
        "TRADE",
        "WATCH",
    ]:
        blocks.append(
            "Legacy Confidence Engine decision is "
            f"{confidence_decision}"
        )

    return list(
        dict.fromkeys(blocks)
    )



def _build_protection_error(
    error: Exception,
    symbol: str,
) -> dict:
    return {
        "status": "error",
        "protected": False,
        "symbol": symbol,
        "reason": "SL/TP protection raised an exception",
        "error": str(error),
        "block_reasons": [],
        "warnings": [],
    }


def _build_protection_verification_error(
    error: Exception,
    symbol: str,
) -> dict:
    return {
        "status": "error",
        "protected": False,
        "symbol": symbol,
        "reason": (
            "Final protection verification raised an exception"
        ),
        "error": str(error),
    }


def _execute_verify_and_protect(
    final_decision: dict,
    symbol: str,
    trade_plan: dict,
) -> dict:
    quantity = _safe_float(
        trade_plan.get("quantity"),
        0.0,
    )

    execution = execute_testnet_trade(
        final_decision=final_decision,
        symbol=symbol,
        quantity=quantity,
        execute_trade=True,
    )

    if not isinstance(execution, dict):
        execution = {
            "status": "error",
            "symbol": symbol,
            "reason": (
                "Testnet Executor returned a non-dictionary response"
            ),
            "raw_response": execution,
        }

    execution = {
        **execution,
        "symbol": str(
            execution.get("symbol", symbol)
        ).upper(),
    }

    verification = execution.get(
        "verification",
        {},
    ) or {}

    execution_status = str(execution.get("status", "")).lower()
    entry_verified = (
        verification.get("filled") is True
        and verification.get("execution_success") is True
        and execution_status not in {
            "blocked",
            "error",
            "skipped",
            "verification_failed",
        }
    )

    if not entry_verified:
        return {
            **execution,
            "status": str(
                execution.get(
                    "status",
                    "verification_failed",
                )
            ),
            "protected": False,
            "protection": {
                "status": "skipped",
                "protected": False,
                "symbol": symbol,
                "reason": (
                    "Protection was not submitted because the entry "
                    "was not verified as fully filled"
                ),
            },
            "protection_verification": {
                "status": "skipped",
                "protected": False,
                "symbol": symbol,
                "reason": (
                    "Protection verification was skipped because "
                    "the entry was not verified as fully filled"
                ),
            },
            "trade_plan": {
                "entry_price": trade_plan.get("entry_price"),
                "stop_loss_price": trade_plan.get(
                    "stop_loss_price"
                ),
                "take_profit_price": trade_plan.get(
                    "take_profit_price"
                ),
                "position_size_usdt": trade_plan.get(
                    "position_size_usdt"
                ),
                "margin_required": trade_plan.get(
                    "margin_required"
                ),
                "leverage": trade_plan.get("leverage"),
                "risk_reward_ratio": trade_plan.get(
                    "risk_reward_ratio"
                ),
            },
        }

    try:
        protection = protect_verified_execution(
            execution=execution,
            trade_plan=trade_plan,
            replace_existing=False,
        )
    except Exception as error:
        protection = _build_protection_error(
            error=error,
            symbol=symbol,
        )

    try:
        protection_verification = inspect_position_protection(
            symbol=symbol,
            stop_loss_price=_safe_float(
                trade_plan.get("stop_loss_price"),
                0.0,
            ),
            take_profit_price=_safe_float(
                trade_plan.get("take_profit_price"),
                0.0,
            ),
        )
    except Exception as error:
        protection_verification = (
            _build_protection_verification_error(
                error=error,
                symbol=symbol,
            )
        )

    protected = (
        protection.get("protected") is True
        and protection_verification.get("protected") is True
    )

    if protected:
        final_status = "protected"
        final_reason = (
            "Entry filled and exchange-side SL/TP "
            "protection verified"
        )
    else:
        final_status = "unsafe"
        final_reason = (
            "Entry filled but complete exchange-side "
            "SL/TP protection was not verified"
        )

    return {
        **execution,
        "status": final_status,
        "reason": final_reason,
        "quantity": quantity,
        "protected": protected,
        "protection": protection,
        "protection_verification": (
            protection_verification
        ),
        "trade_plan": {
            "entry_price": trade_plan.get("entry_price"),
            "stop_loss_price": trade_plan.get(
                "stop_loss_price"
            ),
            "take_profit_price": trade_plan.get(
                "take_profit_price"
            ),
            "position_size_usdt": trade_plan.get(
                "position_size_usdt"
            ),
            "margin_required": trade_plan.get(
                "margin_required"
            ),
            "leverage": trade_plan.get("leverage"),
            "risk_reward_ratio": trade_plan.get(
                "risk_reward_ratio"
            ),
        },
    }


def _attach_trade_integrity(
    result: dict,
) -> dict:
    try:
        result["trade_integrity"] = (
            build_trade_integrity_snapshot(result)
        )
    except Exception as error:
        result["trade_integrity"] = {
            "status": "error",
            "version": "v36",
            "report": None,
            "errors": [str(error)],
            "non_blocking": True,
            "read_only": True,
        }
    return result


def _attach_production_readiness(
    result: dict,
) -> dict:
    try:
        result["production_readiness"] = (
            build_production_readiness_report(
                execute_trade_requested=bool(
                    (
                        result.get("execution")
                        or {}
                    ).get("submitted", False)
                )
            )
        )
    except Exception as error:
        result["production_readiness"] = {
            "status": "NOT_READY",
            "version": "v35.3",
            "ready": False,
            "failed_checks": ["report_generation"],
            "errors": [str(error)],
            "testnet_only": True,
            "read_only": True,
        }
    return result


def _attach_backup_operations(result: dict) -> dict:
    try:
        result["backup_operations"] = build_backup_operations_snapshot()
    except Exception as error:
        result["backup_operations"] = {"status":"error","version":"v35.2","backup_cycle":{"status":"error","errors":[str(error)]},"errors":[str(error)],"non_blocking":True}
    return result


def _attach_operations_snapshot(
    result: dict,
) -> dict:
    try:
        result["operations"] = (
            build_operations_snapshot()
        )
    except Exception as error:
        result["operations"] = {
            "status": "error",
            "version": "v35.1",
            "health": {
                "status": "CRITICAL",
                "healthy": False,
                "errors": [str(error)],
            },
            "supervision": {
                "status": "error",
                "action": "PAUSE",
                "reason": str(error),
            },
            "errors": [str(error)],
            "non_blocking": True,
            "read_only": True,
        }

    return result


def _attach_performance_reporting(
    result: dict,
) -> dict:
    lifecycle = (
        result.get(
            "position_lifecycle",
            {},
        )
        if isinstance(
            result.get(
                "position_lifecycle"
            ),
            dict,
        )
        else {}
    )
    completed_trades = (
        lifecycle.get(
            "completed_trades",
            [],
        )
        if isinstance(
            lifecycle.get(
                "completed_trades"
            ),
            list,
        )
        else []
    )

    try:
        result["performance_reporting"] = (
            build_and_store_performance(
                completed_trades=(
                    completed_trades
                ),
                starting_equity=0.0,
            )
        )
    except Exception as error:
        result["performance_reporting"] = {
            "status": "error",
            "version": "v34",
            "dashboard": {
                "status": "error",
                "version": "v34",
                "error": str(error),
            },
            "snapshot": None,
            "errors": [str(error)],
            "non_blocking": True,
        }

    return result


def _attach_startup_readiness(
    result: dict,
    startup_readiness: dict | None,
) -> dict:
    if startup_readiness is not None:
        result["startup_readiness"] = startup_readiness
    return result


def _attach_notifications(
    result: dict,
) -> dict:
    try:
        result["notifications"] = (
            route_notifications(result)
        )
    except Exception as error:
        result["notifications"] = {
            "status": "error",
            "version": "v32",
            "event_count": 0,
            "stored_count": 0,
            "telegram_sent_count": 0,
            "events": [],
            "errors": [str(error)],
            "non_blocking": True,
        }

    return result


def _attach_dashboard(result: dict) -> dict:
    try:
        result["dashboard"] = build_system_dashboard(result)
    except Exception as error:
        result["dashboard"] = {
            "status": "error",
            "version": "v31",
            "read_only": True,
            "diagnostics_only": True,
            "error": str(error),
        }
    return result


def _attach_service_state(
    result: dict,
    cycle_context: dict | None,
) -> dict:
    if not cycle_context:
        return result

    try:
        result["service_state"] = (
            complete_service_cycle(
                cycle_context=cycle_context,
                result=result,
            )
        )
    except Exception as error:
        result.setdefault(
            "service_state",
            {
                "status": "error",
                "version": "v30",
                "error": str(error),
            },
        )

    return result


def save_result(result: dict) -> None:
    _attach_trade_integrity(result)
    _attach_production_readiness(result)
    _attach_backup_operations(result)
    _attach_operations_snapshot(result)
    _attach_performance_reporting(result)
    _attach_dashboard(result)
    _attach_notifications(result)

    journal_error = None
    memory_error = None

    try:
        save_cycle_result(result)
    except Exception as error:
        journal_error = str(error)

    try:
        save_memory_record(result)
    except Exception as error:
        memory_error = str(error)

    if journal_error or memory_error:
        result.setdefault(
            "save_warnings",
            {},
        )

        if journal_error:
            result["save_warnings"][
                "trade_journal"
            ] = journal_error

        if memory_error:
            result["save_warnings"][
                "memory_engine"
            ] = memory_error


def _inspect_open_position_protection(open_positions: list[dict]) -> tuple[list[dict], list[str]]:
    """Read exchange-side SL/TP protection for each active symbol."""
    results: list[dict] = []
    errors: list[str] = []
    inspected_symbols: set[str] = set()

    for position in open_positions or []:
        if not isinstance(position, dict):
            continue
        symbol = str(position.get("symbol", "")).upper()
        if not symbol or symbol in inspected_symbols:
            continue
        inspected_symbols.add(symbol)
        try:
            results.append(inspect_position_protection(symbol=symbol))
        except Exception as error:
            errors.append(f"{symbol}: {error}")

    return results, errors


def _position_summary(position: dict) -> dict:
    amount = _safe_float(
        position.get(
            "positionAmt",
            position.get(
                "position_amount",
                position.get("quantity", 0.0),
            ),
        ),
        0.0,
    )

    entry_price = _safe_float(
        position.get(
            "entryPrice",
            position.get("entry_price", 0.0),
        ),
        0.0,
    )

    mark_price = _safe_float(
        position.get(
            "markPrice",
            position.get("mark_price", 0.0),
        ),
        0.0,
    )

    unrealized_profit = _safe_float(
        position.get(
            "unRealizedProfit",
            position.get(
                "unrealizedProfit",
                position.get("unrealized_profit", 0.0),
            ),
        ),
        0.0,
    )

    symbol = str(position.get("symbol", "")).upper()
    side = "BUY" if amount > 0 else "SELL"

    return {
        "symbol": symbol,
        "side": side,
        "quantity": abs(amount),
        "signed_quantity": amount,
        "entry_price": entry_price,
        "mark_price": mark_price,
        "unrealized_profit": unrealized_profit,
        "leverage": _safe_float(position.get("leverage"), 0.0),
        "position_side": position.get("positionSide", "BOTH"),
    }


def _manage_existing_positions_guard(
    *,
    open_positions: list,
    raw_open_positions_count: int,
) -> dict:
    """
    Manage and report existing positions before portfolio scanning.

    This is a hard guard: while any live position exists, a new entry cannot
    reach the scanner, candidate-selection, or executor paths.
    """
    partial_take_profit_results = []
    partial_take_profit_error = None

    try:
        partial_take_profit_results = (
            manage_partial_take_profit_for_open_positions(
                positions=open_positions,
                stages=DEFAULT_PARTIAL_TP_STAGES,
                runner_fraction=DEFAULT_PARTIAL_TP_RUNNER_FRACTION,
            )
        )
    except Exception as error:
        partial_take_profit_error = str(error)

    managed_positions = open_positions

    if any(
        item.get("executed") is True
        for item in partial_take_profit_results
        if isinstance(item, dict)
    ):
        refreshed_positions, refresh_error, _ = _get_open_position_data()
        if refresh_error:
            partial_take_profit_error = (
                "Partial TP executed, but position refresh failed: "
                f"{refresh_error}"
            )
        else:
            managed_positions = refreshed_positions

    break_even_results = []
    break_even_error = None

    try:
        break_even_results = manage_break_even_for_open_positions(
            positions=managed_positions,
            trigger_percent=DEFAULT_BREAK_EVEN_TRIGGER_PERCENT,
            buffer_percent=DEFAULT_BREAK_EVEN_BUFFER_PERCENT,
        )
    except Exception as error:
        break_even_error = str(error)

    trailing_stop_results = []
    trailing_stop_error = None

    try:
        trailing_stop_results = manage_trailing_stop_for_open_positions(
            positions=managed_positions,
            activation_percent=DEFAULT_TRAILING_ACTIVATION_PERCENT,
            trailing_distance_percent=DEFAULT_TRAILING_DISTANCE_PERCENT,
            minimum_move_percent=DEFAULT_TRAILING_MINIMUM_MOVE_PERCENT,
        )
    except Exception as error:
        trailing_stop_error = str(error)

    protection_results, protection_errors = (
        _inspect_open_position_protection(managed_positions)
    )

    all_protected = bool(protection_results) and all(
        isinstance(item, dict)
        and item.get("protected") is True
        for item in protection_results
    )

    persistent_state = {
        "status": "skipped",
        "reason": "State synchronisation was not attempted",
        "errors": [],
    }

    try:
        persistent_state = sync_cycle_state(
            open_positions=managed_positions,
            partial_take_profit_results=partial_take_profit_results,
            break_even_results=break_even_results,
            trailing_stop_results=trailing_stop_results,
            protection_results=protection_results,
        )
    except Exception as error:
        persistent_state = {
            "status": "error",
            "reason": "Persistent-state synchronisation failed",
            "errors": [str(error)],
        }

    position_summaries = [
        _position_summary(position)
        for position in managed_positions
        if isinstance(position, dict)
    ]

    guard_reason = (
        "Existing protected position detected; new entry skipped"
        if all_protected
        else (
            "Existing position detected without fully verified protection; "
            "new entry blocked"
        )
    )

    return {
        "status": "skipped" if all_protected else "blocked",
        "reason": guard_reason,
        "mode": "EXISTING_POSITION_GUARD",
        "symbol": (
            position_summaries[0].get("symbol")
            if len(position_summaries) == 1
            else None
        ),
        "open_positions_count": len(managed_positions),
        "raw_open_positions_count": raw_open_positions_count,
        "open_positions": managed_positions,
        "position_status": {
            "status": (
                "protected"
                if all_protected
                else "protection_required"
            ),
            "positions": position_summaries,
            "new_entry_allowed": False,
        },
        "protection_inspection": {
            "protected": all_protected,
            "results": protection_results,
            "errors": protection_errors,
        },
        "partial_take_profit": {
            "results": partial_take_profit_results,
            "error": partial_take_profit_error,
        },
        "break_even": {
            "results": break_even_results,
            "error": break_even_error,
        },
        "trailing_stop": {
            "results": trailing_stop_results,
            "error": trailing_stop_error,
        },
        "persistent_trade_state": persistent_state,
        "execution_blocks": [
            "Existing open position guard prevents a new entry"
        ],
        "execution": {
            "status": "skipped" if all_protected else "blocked",
            "submitted": False,
            "mode": "EXISTING_POSITION_GUARD",
            "reason": guard_reason,
        },
    }



async def _run_auto_testnet_cycle_unlocked(
    quantity: float | None = None,
    execute_trade: bool = False,
    balance: float = DEFAULT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    leverage: float = DEFAULT_LEVERAGE,
    current_daily_pnl: float = 0.0,
    scan_limit: int = 20,
) -> dict:
    scan_limit = max(1, min(_safe_int(scan_limit, 20), 100))
    balance = max(0.0, _safe_float(balance, DEFAULT_BALANCE))
    risk_percent = max(0.0, _safe_float(risk_percent, DEFAULT_RISK_PERCENT))
    leverage = max(0.0, _safe_float(leverage, DEFAULT_LEVERAGE))
    current_daily_pnl = _safe_float(current_daily_pnl, 0.0)

    startup_readiness = evaluate_startup_readiness(
        execute_trade_requested=execute_trade
    )

    cycle_context = begin_service_cycle(
        mode=(
            "TESTNET_EXECUTION"
            if execute_trade
            else "ANALYSIS_ONLY"
        )
    )

    if startup_readiness.get("startup_allowed") is not True:
        result = {
            "status": "blocked",
            "reason": "Production startup validation blocked this cycle",
            "mode": "STARTUP_CONFIGURATION_LOCK",
            "startup_readiness": startup_readiness,
            "execution_blocks": startup_readiness.get("errors", []),
            "execution": {
                "status": "blocked",
                "submitted": False,
                "mode": "SAFETY_LOCKED",
                "reason": "Startup configuration checks did not pass",
            },
        }
        _attach_service_state(result, cycle_context)
        save_result(result)
        return result

    if quantity is not None:
        quantity = _safe_float(quantity, 0.0)
        if quantity <= 0:
            quantity = None

    maximum_position_usdt = (
        balance
        * DEFAULT_MAXIMUM_POSITION_PERCENT
        / 100.0
    )

    # Hard existing-position guard must run before scanning. This prevents
    # duplicate/concurrent entries and keeps the cycle focused on lifecycle
    # management while a position remains open.
    (
        guard_open_positions,
        guard_position_query_error,
        guard_raw_open_positions_count,
    ) = _get_open_position_data()

    if guard_position_query_error:
        position_sync = {
            "status": "blocked",
            "version": "v27",
            "reason": (
                "Live position synchronization was skipped "
                "because Binance positions could not be verified"
            ),
            "mutation_performed": False,
            "execution_submitted": False,
            "errors": [guard_position_query_error],
        }
        lifecycle = {
            "status": "blocked",
            "version": "v25",
            "closed_positions_detected": 0,
            "completed_trades": [],
            "errors": [guard_position_query_error],
        }
    else:
        position_sync = synchronise_live_positions(
            exchange_positions=guard_open_positions
        )
        lifecycle = dict(
            position_sync.get(
                "position_lifecycle",
                {},
            )
        )

    guard_open_orders, guard_order_query_error = (
        _get_open_order_data()
    )

    if guard_order_query_error:
        order_recovery = {
            "status": "blocked",
            "version": "v28",
            "reason": (
                "Order recovery was skipped "
                "because Binance open orders "
                "could not be verified"
            ),
            "mutation_performed": False,
            "execution_submitted": False,
            "orders_cancelled": 0,
            "orders_submitted": 0,
            "errors": [
                guard_order_query_error
            ],
        }
    else:
        order_recovery = recover_open_orders(
            exchange_orders=guard_open_orders,
            open_positions=guard_open_positions,
        )

    execution_watchdog = (
        evaluate_execution_watchdog(
            position_sync=position_sync,
            order_recovery=order_recovery,
        )
    )

    if guard_position_query_error:
        result = {
            "status": "blocked",
            "reason": "Existing-position guard could not verify account state",
            "mode": "EXISTING_POSITION_GUARD",
            "position_query_error": guard_position_query_error,
            "open_positions_count": None,
            "raw_open_positions_count": guard_raw_open_positions_count,
            "position_lifecycle": lifecycle,
            "live_position_sync": position_sync,
            "order_recovery": order_recovery,
            "execution_watchdog": execution_watchdog,
            "execution_blocks": [
                "Open positions could not be verified safely"
            ],
            "execution": {
                "status": "blocked",
                "submitted": False,
                "mode": "SAFETY_LOCKED",
                "reason": (
                    "Execution blocked because existing positions could not "
                    "be verified"
                ),
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    if guard_order_query_error:
        result = {
            "status": "blocked",
            "reason": (
                "Order recovery could not verify "
                "the exchange open-order state"
            ),
            "mode": "ORDER_RECOVERY_LOCK",
            "position_lifecycle": lifecycle,
            "live_position_sync": position_sync,
            "order_recovery": order_recovery,
            "execution_watchdog": execution_watchdog,
            "execution_blocks": [
                "Open orders could not be "
                "verified safely"
            ],
            "execution": {
                "status": "blocked",
                "submitted": False,
                "mode": "SAFETY_LOCKED",
                "reason": (
                    "Execution blocked because "
                    "open orders could not be "
                    "verified"
                ),
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    if execution_watchdog.get(
        "allowed"
    ) is not True:
        result = {
            "status": "blocked",
            "reason": (
                "Execution Watchdog blocked "
                "the cycle"
            ),
            "mode": "EXECUTION_WATCHDOG_LOCK",
            "position_lifecycle": lifecycle,
            "live_position_sync": position_sync,
            "order_recovery": order_recovery,
            "execution_watchdog": (
                execution_watchdog
            ),
            "execution_blocks": (
                execution_watchdog.get(
                    "block_reasons",
                    [],
                )
            ),
            "execution": {
                "status": "blocked",
                "submitted": False,
                "mode": "SAFETY_LOCKED",
                "reason": (
                    "Pre-scan execution health "
                    "checks did not pass"
                ),
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    if guard_open_positions:
        result = _manage_existing_positions_guard(
            open_positions=guard_open_positions,
            raw_open_positions_count=guard_raw_open_positions_count,
        )
        result["position_lifecycle"] = lifecycle
        result["live_position_sync"] = position_sync
        result["order_recovery"] = order_recovery
        result["execution_watchdog"] = execution_watchdog
        result["performance_analytics"] = build_performance_snapshot(hours=24)
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    daily_risk = evaluate_daily_risk(balance=balance)
    performance_analytics = daily_risk.get(
        "analytics",
        build_performance_snapshot(hours=24),
    )

    if daily_risk.get("allowed") is not True:
        result = {
            "status": "blocked",
            "reason": daily_risk.get(
                "reason",
                "Daily risk manager blocked new entries",
            ),
            "mode": "DAILY_RISK_LOCK",
            "symbol": None,
            "open_positions_count": 0,
            "position_lifecycle": lifecycle,
            "live_position_sync": position_sync,
            "order_recovery": order_recovery,
            "execution_watchdog": execution_watchdog,
            "daily_risk": daily_risk,
            "performance_analytics": performance_analytics,
            "execution_blocks": [
                daily_risk.get(
                    "reason",
                    "Daily risk manager blocked execution",
                )
            ],
            "execution": {
                "status": "blocked",
                "submitted": False,
                "mode": "DAILY_RISK_LOCK",
                "reason": daily_risk.get(
                    "reason",
                    "Daily risk manager blocked execution",
                ),
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    try:
        scan = await scan_portfolio(
            limit=scan_limit,
            maximum_position_usdt=maximum_position_usdt,
        )
    except Exception as error:
        result = {
            "status": "error",
            "reason": "Portfolio scan raised an exception",
            "error": str(error),
            "execution": {
                "status": "blocked",
                "mode": "SAFETY_LOCKED",
                "reason": "Execution blocked because portfolio scanning failed",
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    if not isinstance(scan, dict):
        result = {
            "status": "error",
            "reason": "Portfolio Scanner returned a non-dictionary response",
            "raw_scan": scan,
            "execution": {
                "status": "blocked",
                "mode": "SAFETY_LOCKED",
                "reason": "Execution blocked because scan output was invalid",
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    # Query positions before candidate selection because Risk Engine approval
    # depends on the current concurrent-position count.
    (
        selection_open_positions,
        selection_position_query_error,
        selection_raw_open_positions_count,
    ) = _get_open_position_data()

    if selection_position_query_error:
        result = {
            "status": "blocked",
            "reason": (
                "Candidate selection could not safely verify open positions"
            ),
            "scan": scan,
            "position_query_error": selection_position_query_error,
            "raw_open_positions_count": selection_raw_open_positions_count,
            "execution": {
                "status": "blocked",
                "mode": "SAFETY_LOCKED",
                "reason": (
                    "Execution blocked because open positions could not "
                    "be verified"
                ),
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    candidates = scan.get("executable_ranked", [])
    if not isinstance(candidates, list):
        candidates = []

    # Backward-compatible fallback for older scanner payloads.
    if not candidates:
        scanner_best_setup = scan.get("best_setup")
        if isinstance(scanner_best_setup, dict) and scanner_best_setup:
            candidates = [scanner_best_setup]

    candidate_attempts = []
    selected_evaluation = None

    for rank, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict) or not candidate:
            continue

        try:
            evaluation = await _evaluate_candidate_for_selection(
                candidate,
                quantity=quantity,
                balance=balance,
                risk_percent=risk_percent,
                leverage=leverage,
                current_daily_pnl=current_daily_pnl,
                open_positions_count=len(selection_open_positions),
                open_positions=selection_open_positions,
            )
        except Exception as error:
            evaluation = {
                "symbol": str(
                    candidate.get("symbol", "")
                ).upper(),
                "accepted": False,
                "block_reasons": [
                    "Candidate evaluation raised an exception"
                ],
                "error": str(error),
                "summary": {
                    "ai_score": _safe_float(
                        candidate.get("ai_score", {}).get("score"),
                        0.0,
                    ),
                },
            }

        candidate_attempts.append({
            "rank": rank,
            "symbol": evaluation.get("symbol"),
            "accepted": evaluation.get("accepted") is True,
            "block_reasons": evaluation.get("block_reasons", []),
            "error": evaluation.get("error"),
            "summary": evaluation.get("summary", {}),
            "account_protection": evaluation.get(
                "account_protection"
            ),
        })

        if evaluation.get("accepted") is True:
            selected_evaluation = evaluation
            break

    if not selected_evaluation:
        result = {
            "status": "skipped",
            "reason": (
                "No ranked executable candidate passed all final "
                "pre-execution safety gates"
            ),
            "scan": scan,
            "candidate_attempts": candidate_attempts,
            "candidates_evaluated": len(candidate_attempts),
            "execution": {
                "status": "skipped",
                "mode": "NO_EXECUTABLE_CANDIDATE",
                "reason": (
                    "Every ranked candidate was rejected by final "
                    "validation, risk, sizing, or account protection"
                ),
            },
        }
        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
        save_result(result)
        return result

    best_setup = selected_evaluation["candidate"]
    scan["best_setup"] = best_setup
    scan["selected_candidate_rank"] = next(
        (
            item["rank"]
            for item in candidate_attempts
            if item.get("accepted") is True
        ),
        None,
    )
    scan["candidate_attempts"] = candidate_attempts

    symbol = str(
        best_setup.get("symbol", "")
    ).upper()

    price = _safe_float(
        best_setup.get("price"),
        0.0,
    )

    ai_score = best_setup.get(
        "ai_score",
        {},
    )

    final_decision = best_setup.get(
        "final_decision",
        {},
    )

    # Portfolio Scanner provides an initial validation result, but Validator v3
    # needs the Confirmation Engine output for its adaptive MACD override.
    initial_validation = best_setup.get(
        "validation",
        {},
    )

    optimized_strategy = _get_strategy(
        symbol
    )

    confidence = calculate_confidence(
        symbol,
        ai_score,
    )

    confirmation = evaluate_trade_confirmation(
        ai_score=ai_score,
        order_flow=best_setup.get(
            "order_flow",
        ),
        liquidity_trend=best_setup.get(
            "liquidity_trend",
        ),
        liquidity_sweep=best_setup.get(
            "liquidity_sweep",
        ),
        absorption=best_setup.get(
            "absorption",
        ),
        iceberg=best_setup.get(
            "iceberg",
        ),
        whale_activity=best_setup.get(
            "whale_activity",
        ),
        market_structure=best_setup.get(
            "market_structure",
        ),
        volume_profile=best_setup.get(
            "volume_profile",
        ),
        vwap=best_setup.get(
            "vwap",
        ),
        fair_value_gaps=best_setup.get(
            "fair_value_gaps",
        ),
        technical=best_setup.get(
            "technical",
        ),
        multi_timeframe=best_setup.get(
            "multi_timeframe",
        ),
    )

    confirmation = _normalize_confirmation(
        confirmation
    )

    (
        validator_final_decision,
        validator_ai_score,
        validator_technical,
    ) = _build_validator_inputs(
        best_setup=best_setup,
        final_decision=final_decision,
        ai_score=ai_score,
        confirmation=confirmation,
    )

    validation = validate_trade(
        final_decision=validator_final_decision,
        ai_score=validator_ai_score,
        order_book=best_setup.get(
            "order_book",
            {},
        ),
        technical=validator_technical,
        multi_timeframe=best_setup.get(
            "multi_timeframe",
            {},
        ),
    )

    validation["initial_scanner_validation"] = initial_validation

    trade_quality = evaluate_trade_quality(
        order_book=best_setup.get(
            "order_book",
            {},
        ),
        order_flow=best_setup.get(
            "order_flow",
            {},
        ),
        liquidity_trend=best_setup.get(
            "liquidity_trend",
        ),
        confidence=confidence,
        validation=validation,
        direction=final_decision.get(
            "decision",
            "HOLD",
        ),
    )

    (
        open_positions,
        position_query_error,
        raw_open_positions_count,
    ) = _get_open_position_data()

    open_positions_count = len(
        open_positions
    )

    try:
        position_status = manage_open_positions(
            final_decision,
            symbol,
        )
    except Exception as error:
        position_status = {
            "status": "error",
            "reason": "Position Manager raised an exception",
            "error": str(error),
        }

    if not isinstance(position_status, dict):
        position_status = {
            "status": "error",
            "reason": "Position Manager returned a non-dictionary response",
            "raw_response": position_status,
        }

    partial_take_profit_results = []
    partial_take_profit_error = None

    if open_positions:
        try:
            partial_take_profit_results = (
                manage_partial_take_profit_for_open_positions(
                    positions=open_positions,
                    stages=DEFAULT_PARTIAL_TP_STAGES,
                    runner_fraction=(
                        DEFAULT_PARTIAL_TP_RUNNER_FRACTION
                    ),
                )
            )

            # A successful partial close changes the exchange quantity.
            # Refresh positions before break-even and trailing-stop managers
            # so they never submit protection using stale quantities.
            if any(
                item.get("executed") is True
                for item in partial_take_profit_results
                if isinstance(item, dict)
            ):
                (
                    open_positions,
                    refresh_error,
                    raw_open_positions_count,
                ) = _get_open_position_data()
                open_positions_count = len(open_positions)
                if refresh_error:
                    partial_take_profit_error = (
                        "Partial TP executed, but position refresh failed: "
                        f"{refresh_error}"
                    )
        except Exception as error:
            partial_take_profit_error = str(error)

    break_even_results = []
    break_even_error = None

    if open_positions:
        try:
            break_even_results = (
                manage_break_even_for_open_positions(
                    positions=open_positions,
                    trigger_percent=(
                        DEFAULT_BREAK_EVEN_TRIGGER_PERCENT
                    ),
                    buffer_percent=(
                        DEFAULT_BREAK_EVEN_BUFFER_PERCENT
                    ),
                )
            )
        except Exception as error:
            break_even_error = str(error)

    trailing_stop_results = []
    trailing_stop_error = None

    if open_positions:
        try:
            trailing_stop_results = (
                manage_trailing_stop_for_open_positions(
                    positions=open_positions,
                    activation_percent=(
                        DEFAULT_TRAILING_ACTIVATION_PERCENT
                    ),
                    trailing_distance_percent=(
                        DEFAULT_TRAILING_DISTANCE_PERCENT
                    ),
                    minimum_move_percent=(
                        DEFAULT_TRAILING_MINIMUM_MOVE_PERCENT
                    ),
                )
            )
        except Exception as error:
            trailing_stop_error = str(error)

    protection_results, protection_inspection_errors = (
        _inspect_open_position_protection(open_positions)
    )

    persistent_state = {
        "status": "skipped",
        "reason": "State synchronisation was not attempted",
        "errors": [],
    }

    try:
        persistent_state = sync_cycle_state(
            open_positions=open_positions,
            partial_take_profit_results=(
                partial_take_profit_results
            ),
            break_even_results=break_even_results,
            trailing_stop_results=trailing_stop_results,
            protection_results=protection_results,
        )
    except Exception as error:
        persistent_state = {
            "status": "error",
            "reason": "Persistent-state synchronisation failed",
            "errors": [str(error)],
        }

    # Reuse the exact bounded risk decision that passed
    # ranked-candidate selection. This prevents sizing drift.
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

    trade_plan = dict(
        selected_evaluation.get(
            "trade_plan",
            {},
        )
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
        "live_position_sync": position_sync,
        "order_recovery": order_recovery,
        "execution_watchdog": execution_watchdog,
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

        _attach_startup_readiness(
            result,
            startup_readiness,
        )
        _attach_service_state(
            result,
            cycle_context,
        )
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

    _attach_startup_readiness(
        result,
        startup_readiness,
    )
    _attach_service_state(
        result,
        cycle_context,
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
        concurrency_context = begin_service_cycle(
            mode="CONCURRENCY_GUARD"
        )
        _attach_service_state(
            result,
            concurrency_context,
        )
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
        emergency_context = begin_service_cycle(
            mode="SAFETY_LOCKED"
        )
        _attach_service_state(
            result,
            emergency_context,
        )
        save_result(result)
        return result
    finally:
        _CYCLE_LOCK.release()