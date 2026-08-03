"""TitanAI v24 daily risk and trading-lock manager."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.trader.performance_analytics import build_performance_snapshot
from app.trader.persistent_trade_state import get_system_lock, set_system_lock

DEFAULT_DAILY_PROFIT_TARGET_USDT = 5.0
DEFAULT_DAILY_LOSS_LIMIT_PERCENT = 3.0
DEFAULT_MAX_TRADES_PER_DAY = 5
DEFAULT_MAX_CONSECUTIVE_LOSSES = 3
DEFAULT_COOLDOWN_MINUTES = 120


def _parse(value: str | None):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def evaluate_daily_risk(
    *,
    balance: float,
    daily_profit_target_usdt: float = DEFAULT_DAILY_PROFIT_TARGET_USDT,
    daily_loss_limit_percent: float = DEFAULT_DAILY_LOSS_LIMIT_PERCENT,
    max_trades_per_day: int = DEFAULT_MAX_TRADES_PER_DAY,
    max_consecutive_losses: int = DEFAULT_MAX_CONSECUTIVE_LOSSES,
    cooldown_minutes: int = DEFAULT_COOLDOWN_MINUTES,
) -> dict:
    analytics = build_performance_snapshot(hours=24)
    now = datetime.now(timezone.utc)

    existing = get_system_lock("DAILY_RISK")
    if existing and existing.get("locked"):
        expires = _parse(existing.get("expires_at"))
        if expires is None or expires > now:
            return {
                "status": "locked",
                "allowed": False,
                "reason": existing.get("reason") or "Daily risk lock active",
                "lock": existing,
                "analytics": analytics,
            }
        set_system_lock(
            "DAILY_RISK",
            locked=False,
            reason="Cooldown expired",
            metadata={"previous_lock": existing},
        )

    loss_limit = max(0.0, balance) * max(0.0, daily_loss_limit_percent) / 100.0

    reason = None
    expires_at = None

    if analytics["net_pnl"] >= daily_profit_target_usdt:
        reason = "Daily profit target reached"
        tomorrow = (now + timedelta(days=1)).date()
        expires_at = datetime.combine(
            tomorrow, datetime.min.time(), tzinfo=timezone.utc
        ).isoformat()
    elif analytics["net_pnl"] <= -loss_limit and loss_limit > 0:
        reason = "Daily loss limit reached"
        tomorrow = (now + timedelta(days=1)).date()
        expires_at = datetime.combine(
            tomorrow, datetime.min.time(), tzinfo=timezone.utc
        ).isoformat()
    elif analytics["trade_count"] >= max_trades_per_day:
        reason = "Maximum trades per 24 hours reached"
        expires_at = (now + timedelta(hours=24)).isoformat()
    elif analytics["consecutive_losses"] >= max_consecutive_losses:
        reason = "Consecutive-loss cooldown activated"
        expires_at = (now + timedelta(minutes=cooldown_minutes)).isoformat()

    if reason:
        lock = set_system_lock(
            "DAILY_RISK",
            locked=True,
            reason=reason,
            expires_at=expires_at,
            metadata={"analytics": analytics},
        )
        return {
            "status": "locked",
            "allowed": False,
            "reason": reason,
            "lock": lock,
            "analytics": analytics,
        }

    return {
        "status": "allowed",
        "allowed": True,
        "reason": "Daily risk limits allow a new entry",
        "analytics": analytics,
    }