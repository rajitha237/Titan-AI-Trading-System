"""
TitanAI Risk Engine v2

Safety-focused risk planning with backward compatibility.

Features:
- Risk-based position sizing
- Stop-loss and take-profit validation
- Minimum risk-reward validation
- Dynamic leverage limits
- Maximum position-size protection
- Daily-loss protection
- Concurrent-position protection
- Confirmation Engine approval support
- SMALL_TRADE mode
- Testnet/live safety modes
- Zero and invalid-value protection
"""

from typing import Any


DEFAULT_BALANCE = 30.0
DEFAULT_RISK_PERCENT = 1.0
DEFAULT_LEVERAGE = 5.0
DEFAULT_STOP_LOSS_PERCENT = 0.8
DEFAULT_TAKE_PROFIT_PERCENT = 2.4

DEFAULT_MIN_RISK_REWARD = 1.0
DEFAULT_MAX_RISK_PERCENT = 2.0
DEFAULT_MAX_LEVERAGE = 5.0
DEFAULT_MAX_POSITION_PERCENT = 25.0

DEFAULT_MAX_DAILY_LOSS_PERCENT = 3.0
DEFAULT_MAX_CONCURRENT_POSITIONS = 1

SMALL_TRADE_MULTIPLIER = 0.5


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        result = float(value)

        if result != result:
            return default

        if result in [float("inf"), float("-inf")]:
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


def _clamp(
    value: float,
    minimum: float,
    maximum: float,
) -> float:
    return max(
        minimum,
        min(value, maximum),
    )


def _get_confirmation_details(
    confirmation: dict | None,
) -> tuple[str, float, bool]:
    """
    Read confirmation results with backward compatibility.

    Supported formats:

    New/standard:
        {
            "decision": "APPROVE",
            "confirmation_score": 100,
            "passed": True,
        }

    Existing TitanAI format:
        {
            "decision": "APPROVE",
            "score": 100,
            "approved": True,
        }
    """
    confirmation = confirmation or {}

    decision = str(
        confirmation.get("decision", "UNKNOWN")
    ).upper()

    score = _safe_float(
        confirmation.get(
            "confirmation_score",
            confirmation.get("score", 0.0),
        ),
        0.0,
    )

    passed = bool(
        confirmation.get(
            "passed",
            confirmation.get("approved", False),
        )
    )

    return decision, score, passed


def _calculate_dynamic_leverage(
    requested_leverage: float,
    max_leverage: float,
    confirmation: dict | None,
) -> float:
    safe_requested = _clamp(
        requested_leverage,
        1.0,
        max_leverage,
    )

    if not confirmation:
        return safe_requested

    decision, score, passed = (
        _get_confirmation_details(confirmation)
    )

    if not passed or decision != "APPROVE":
        return 1.0

    if score >= 90:
        confirmation_limit = max_leverage
    elif score >= 80:
        confirmation_limit = min(
            max_leverage,
            4.0,
        )
    elif score >= 75:
        confirmation_limit = min(
            max_leverage,
            3.0,
        )
    else:
        confirmation_limit = 1.0

    return _clamp(
        min(
            safe_requested,
            confirmation_limit,
        ),
        1.0,
        max_leverage,
    )


def calculate_risk_plan(
    balance: float = DEFAULT_BALANCE,
    risk_percent: float = DEFAULT_RISK_PERCENT,
    leverage: float = DEFAULT_LEVERAGE,
    stop_loss_percent: float = DEFAULT_STOP_LOSS_PERCENT,
    take_profit_percent: float = DEFAULT_TAKE_PROFIT_PERCENT,
    confirmation: dict | None = None,
    require_confirmation: bool = False,
    trade_quality_action: str | None = None,
    current_daily_pnl: float = 0.0,
    open_positions_count: int = 0,
    minimum_risk_reward: float = DEFAULT_MIN_RISK_REWARD,
    maximum_risk_percent: float = DEFAULT_MAX_RISK_PERCENT,
    maximum_leverage: float = DEFAULT_MAX_LEVERAGE,
    maximum_position_percent: float = (
        DEFAULT_MAX_POSITION_PERCENT
    ),
    maximum_daily_loss_percent: float = (
        DEFAULT_MAX_DAILY_LOSS_PERCENT
    ),
    maximum_concurrent_positions: int = (
        DEFAULT_MAX_CONCURRENT_POSITIONS
    ),
    mode: str = "TESTNET",
) -> dict:
    block_reasons = []
    warnings = []

    balance = _safe_float(
        balance,
        DEFAULT_BALANCE,
    )

    requested_risk_percent = _safe_float(
        risk_percent,
        DEFAULT_RISK_PERCENT,
    )

    requested_leverage = _safe_float(
        leverage,
        DEFAULT_LEVERAGE,
    )

    stop_loss_percent = _safe_float(
        stop_loss_percent,
        DEFAULT_STOP_LOSS_PERCENT,
    )

    take_profit_percent = _safe_float(
        take_profit_percent,
        DEFAULT_TAKE_PROFIT_PERCENT,
    )

    current_daily_pnl = _safe_float(
        current_daily_pnl,
        0.0,
    )

    open_positions_count = _safe_int(
        open_positions_count,
        0,
    )

    minimum_risk_reward = max(
        0.0,
        _safe_float(
            minimum_risk_reward,
            DEFAULT_MIN_RISK_REWARD,
        ),
    )

    maximum_risk_percent = max(
        0.1,
        _safe_float(
            maximum_risk_percent,
            DEFAULT_MAX_RISK_PERCENT,
        ),
    )

    maximum_leverage = max(
        1.0,
        _safe_float(
            maximum_leverage,
            DEFAULT_MAX_LEVERAGE,
        ),
    )

    maximum_position_percent = _clamp(
        _safe_float(
            maximum_position_percent,
            DEFAULT_MAX_POSITION_PERCENT,
        ),
        1.0,
        100.0,
    )

    maximum_daily_loss_percent = max(
        0.1,
        _safe_float(
            maximum_daily_loss_percent,
            DEFAULT_MAX_DAILY_LOSS_PERCENT,
        ),
    )

    maximum_concurrent_positions = max(
        1,
        _safe_int(
            maximum_concurrent_positions,
            DEFAULT_MAX_CONCURRENT_POSITIONS,
        ),
    )

    mode = str(mode or "TESTNET").upper()

    if mode not in [
        "ANALYSIS",
        "TESTNET",
        "LIVE",
    ]:
        warnings.append(
            f"Unknown risk mode '{mode}', using TESTNET"
        )
        mode = "TESTNET"

    if balance <= 0:
        block_reasons.append(
            "Account balance must be greater than zero"
        )

    if stop_loss_percent <= 0:
        block_reasons.append(
            "Stop-loss percentage must be greater than zero"
        )

    if take_profit_percent <= 0:
        block_reasons.append(
            "Take-profit percentage must be greater than zero"
        )

    safe_risk_percent = _clamp(
        requested_risk_percent,
        0.1,
        maximum_risk_percent,
    )

    if requested_risk_percent > maximum_risk_percent:
        warnings.append(
            "Requested risk percentage was reduced to "
            "the configured maximum"
        )

    confirmation_decision, confirmation_score, (
        confirmation_passed
    ) = _get_confirmation_details(
        confirmation
    )

    if require_confirmation:
        if confirmation_decision != "APPROVE":
            block_reasons.append(
                "Confirmation Engine decision is not APPROVE"
            )

        if not confirmation_passed:
            block_reasons.append(
                "Confirmation Engine did not pass the setup"
            )

    effective_leverage = _calculate_dynamic_leverage(
        requested_leverage=requested_leverage,
        max_leverage=maximum_leverage,
        confirmation=confirmation,
    )

    if effective_leverage < requested_leverage:
        warnings.append(
            "Requested leverage was reduced by risk controls"
        )

    risk_amount = (
        balance
        * safe_risk_percent
        / 100
        if balance > 0
        else 0.0
    )

    stop_loss_fraction = (
        stop_loss_percent / 100
        if stop_loss_percent > 0
        else 0.0
    )

    raw_position_size = (
        risk_amount / stop_loss_fraction
        if stop_loss_fraction > 0
        else 0.0
    )

    leverage_position_cap = (
        balance * effective_leverage
        if balance > 0
        else 0.0
    )

    # Capital-preservation rule:
    # maximum_position_percent is measured against the account balance,
    # not against the leveraged buying-power cap. This prevents leverage
    # from silently increasing the configured account exposure.
    account_position_cap = (
        balance
        * maximum_position_percent
        / 100
        if balance > 0
        else 0.0
    )

    position_size = min(
        raw_position_size,
        leverage_position_cap,
        account_position_cap,
    )

    trade_quality_action = str(
        trade_quality_action or "TRADE"
    ).upper()

    small_trade_applied = False

    if trade_quality_action == "SMALL_TRADE":
        position_size *= SMALL_TRADE_MULTIPLIER
        risk_amount *= SMALL_TRADE_MULTIPLIER
        small_trade_applied = True

    elif trade_quality_action in [
        "REJECT",
        "WATCH",
    ]:
        block_reasons.append(
            f"Trade Quality action is {trade_quality_action}"
        )

    risk_reward_ratio = (
        take_profit_percent / stop_loss_percent
        if stop_loss_percent > 0
        else 0.0
    )

    if risk_reward_ratio < minimum_risk_reward:
        block_reasons.append(
            "Risk-reward ratio is below the configured minimum"
        )

    maximum_daily_loss_amount = (
        balance
        * maximum_daily_loss_percent
        / 100
        if balance > 0
        else 0.0
    )

    daily_loss_used = max(
        0.0,
        -current_daily_pnl,
    )

    remaining_daily_loss = max(
        0.0,
        maximum_daily_loss_amount - daily_loss_used,
    )

    if (
        maximum_daily_loss_amount > 0
        and daily_loss_used
        >= maximum_daily_loss_amount
    ):
        block_reasons.append(
            "Maximum daily-loss limit has been reached"
        )

    if risk_amount > remaining_daily_loss:
        block_reasons.append(
            "Planned risk exceeds the remaining daily-loss allowance"
        )

    if (
        open_positions_count
        >= maximum_concurrent_positions
    ):
        block_reasons.append(
            "Maximum concurrent-position limit has been reached"
        )

    if position_size <= 0:
        block_reasons.append(
            "Calculated position size is zero or invalid"
        )

    if risk_amount <= 0:
        block_reasons.append(
            "Calculated risk amount is zero or invalid"
        )

    block_reasons = list(
        dict.fromkeys(block_reasons)
    )

    warnings = list(
        dict.fromkeys(warnings)
    )

    approved = len(block_reasons) == 0

    if mode == "ANALYSIS":
        execution_allowed = False
        execution_mode = "RISK_ANALYSIS_ONLY"

    elif mode == "TESTNET":
        execution_allowed = approved
        execution_mode = "TESTNET_ALLOWED"

    else:
        execution_allowed = (
            approved
            and require_confirmation
            and confirmation_passed
            and confirmation_decision == "APPROVE"
        )

        execution_mode = (
            "LIVE_ALLOWED"
            if execution_allowed
            else "LIVE_SAFETY_LOCKED"
        )

    max_loss_if_sl_hit = (
        position_size
        * stop_loss_percent
        / 100
    )

    estimated_profit_if_tp_hit = (
        position_size
        * take_profit_percent
        / 100
    )

    margin_required = (
        position_size / effective_leverage
        if effective_leverage > 0
        else 0.0
    )

    return {
        "status": (
            "approved"
            if approved
            else "blocked"
        ),
        "approved": approved,
        "execution_allowed": execution_allowed,
        "mode": mode,
        "execution_mode": execution_mode,

        "balance": round(balance, 4),

        "requested_risk_percent": round(
            requested_risk_percent,
            4,
        ),
        "risk_percent": round(
            safe_risk_percent,
            4,
        ),
        "maximum_risk_percent": round(
            maximum_risk_percent,
            4,
        ),
        "risk_amount": round(
            risk_amount,
            4,
        ),

        "requested_leverage": round(
            requested_leverage,
            4,
        ),
        "leverage": round(
            effective_leverage,
            4,
        ),
        "maximum_leverage": round(
            maximum_leverage,
            4,
        ),

        "raw_position_size": round(
            raw_position_size,
            4,
        ),
        "position_size": round(
            position_size,
            4,
        ),
        "position_size_usdt": round(
            position_size,
            4,
        ),
        "margin_required": round(
            margin_required,
            4,
        ),
        "maximum_position_percent": round(
            maximum_position_percent,
            2,
        ),
        "leverage_position_cap": round(
            leverage_position_cap,
            4,
        ),
        "account_position_cap": round(
            account_position_cap,
            4,
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
        "minimum_risk_reward": round(
            minimum_risk_reward,
            4,
        ),

        "max_loss_if_sl_hit": round(
            max_loss_if_sl_hit,
            4,
        ),
        "estimated_profit_if_tp_hit": round(
            estimated_profit_if_tp_hit,
            4,
        ),

        "current_daily_pnl": round(
            current_daily_pnl,
            4,
        ),
        "daily_loss_used": round(
            daily_loss_used,
            4,
        ),
        "maximum_daily_loss_percent": round(
            maximum_daily_loss_percent,
            4,
        ),
        "maximum_daily_loss_amount": round(
            maximum_daily_loss_amount,
            4,
        ),
        "remaining_daily_loss": round(
            remaining_daily_loss,
            4,
        ),

        "open_positions_count": (
            open_positions_count
        ),
        "maximum_concurrent_positions": (
            maximum_concurrent_positions
        ),

        "confirmation_required": (
            require_confirmation
        ),
        "confirmation_passed": (
            confirmation_passed
        ),
        "confirmation_decision": (
            confirmation_decision
        ),
        "confirmation_score": round(
            confirmation_score,
            2,
        ),

        "trade_quality_action": (
            trade_quality_action
        ),
        "small_trade_applied": (
            small_trade_applied
        ),
        "small_trade_multiplier": (
            SMALL_TRADE_MULTIPLIER
            if small_trade_applied
            else 1.0
        ),

        "block_reasons": block_reasons,
        "warnings": warnings,
    }