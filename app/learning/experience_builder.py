"""Build normalized learning records from completed TitanAI trades."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.learning.experience_store import save_experience


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        if number != number or number in (float("inf"), float("-inf")):
            return default
        return number
    except (TypeError, ValueError):
        return default


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _text(mapping: dict, *keys: str, default: str = "UNKNOWN") -> str:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return str(value).upper()
    return default


def _session(value: str | None) -> str:
    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        hour = parsed.astimezone(timezone.utc).hour
    except (TypeError, ValueError):
        return "UNKNOWN"

    if hour < 8:
        return "ASIA"
    if hour < 13:
        return "LONDON"
    if hour < 21:
        return "NEW_YORK"
    return "LATE_US"


def _extract_context(completed_trade: dict) -> dict:
    metadata = _mapping(completed_trade.get("metadata"))
    state = _mapping(metadata.get("last_position_state"))
    state_metadata = _mapping(state.get("metadata"))

    candidate = _mapping(
        state_metadata.get("candidate")
        or state_metadata.get("best_setup")
        or state_metadata.get("market_snapshot")
    )

    technical = _mapping(candidate.get("technical"))
    order_flow = _mapping(candidate.get("order_flow"))
    order_book = _mapping(candidate.get("order_book"))
    regime = _mapping(candidate.get("live_market_regime"))
    strategy = _mapping(candidate.get("institutional_strategy"))
    confirmation = _mapping(
        state_metadata.get("confirmation")
        or candidate.get("confirmation")
    )
    adaptive = _mapping(candidate.get("adaptive_score"))
    research = _mapping(candidate.get("research_confluence"))

    return {
        "state": state,
        "state_metadata": state_metadata,
        "candidate": candidate,
        "technical": technical,
        "order_flow": order_flow,
        "order_book": order_book,
        "regime": regime,
        "strategy": strategy,
        "confirmation": confirmation,
        "adaptive": adaptive,
        "research": research,
    }


def build_experience_record(completed_trade: dict) -> dict:
    """Convert one closed trade into a stable learning schema."""
    context = _extract_context(completed_trade)
    candidate = context["candidate"]
    technical = context["technical"]
    order_flow = context["order_flow"]
    order_book = context["order_book"]
    regime = context["regime"]
    strategy = context["strategy"]
    confirmation = context["confirmation"]
    adaptive = context["adaptive"]
    research = context["research"]
    state_metadata = context["state_metadata"]

    trade_id = str(completed_trade.get("trade_id", "")).strip()
    symbol = str(completed_trade.get("symbol", "")).upper()
    side = str(completed_trade.get("side", "")).upper()
    closed_at = completed_trade.get("closed_at")

    fingerprint = {
        "symbol": symbol,
        "side": side,
        "session": _session(closed_at),
        "market_regime": _text(
            regime,
            "regime",
            "market_regime",
        ),
        "strategy": _text(
            strategy,
            "selected_strategy",
            "strategy",
        ),
        "technical_trend": _text(
            technical,
            "trend",
            "ema_trend",
        ),
        "macd_direction": _text(
            technical,
            "macd_direction",
            "macd_signal",
        ),
        "order_flow_pressure": _text(
            order_flow,
            "pressure",
            "signal",
        ),
        "order_book_pressure": _text(
            order_book,
            "pressure",
            "signal",
        ),
        "research_decision": _text(
            research,
            "decision",
            "status",
        ),
        "rsi_bucket": round(
            _safe_float(technical.get("rsi"), 50.0) / 10.0
        ) * 10,
        "adx_bucket": round(
            _safe_float(technical.get("adx"), 0.0) / 5.0
        ) * 5,
        "delta_bucket": round(
            _safe_float(order_flow.get("delta_ratio"), 0.0),
            1,
        ),
    }

    identity = trade_id or "|".join(
        [
            symbol,
            side,
            str(completed_trade.get("opened_at")),
            str(closed_at),
        ]
    )
    experience_id = "exp-" + hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:24]

    ai_score = _safe_float(
        adaptive.get(
            "final_score",
            _mapping(candidate.get("ai_score")).get("score"),
        )
    )
    confirmation_score = _safe_float(
        confirmation.get(
            "confirmation_score",
            confirmation.get("score"),
        )
    )

    return {
        "experience_id": experience_id,
        "created_at": closed_at or datetime.now(
            timezone.utc
        ).isoformat(),
        "trade_id": trade_id or None,
        "symbol": symbol,
        "side": side,
        "outcome": str(
            completed_trade.get("outcome", "BREAKEVEN")
        ).upper(),
        "net_pnl": _safe_float(completed_trade.get("net_pnl")),
        "strategy": fingerprint["strategy"],
        "market_regime": fingerprint["market_regime"],
        "session": fingerprint["session"],
        "entry_price": _safe_float(
            completed_trade.get("entry_price")
        ),
        "exit_price": _safe_float(
            completed_trade.get("exit_price")
        ),
        "duration_seconds": _safe_float(
            completed_trade.get("duration_seconds")
        ),
        "ai_score": ai_score,
        "confirmation_score": confirmation_score,
        "pattern_fingerprint": fingerprint,
        "context": {
            "exit_reason": completed_trade.get("exit_reason"),
            "exit_price_source": completed_trade.get(
                "exit_price_source"
            ),
            "quantity": completed_trade.get("closed_quantity"),
            "risk_plan": state_metadata.get("risk_plan"),
            "trade_plan": state_metadata.get("trade_plan"),
            "candidate": candidate,
        },
        "raw_completed_trade": completed_trade,
    }


def save_experience_from_completed_trade(
    completed_trade: dict,
) -> dict:
    record = build_experience_record(completed_trade)
    saved = save_experience(record)
    return {
        **saved,
        "record": record,
    }
