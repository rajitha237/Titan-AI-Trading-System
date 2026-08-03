"""Build live fingerprints compatible with Experience Learning v1."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        number = float(value)

        if number != number:
            return default

        if number in {
            float("inf"),
            float("-inf"),
        }:
            return default

        return number

    except (TypeError, ValueError):
        return default


def _mapping(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _directional_text(
    value: Any,
    *keys: str,
    default: str = "UNKNOWN",
) -> str:
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)

            if candidate not in {
                None,
                "",
            }:
                return str(candidate).upper()

        return default

    if value not in {
        None,
        "",
    }:
        return str(value).upper()

    return default


def _session_name(
    now: datetime | None = None,
) -> str:
    current = now or datetime.now(timezone.utc)
    hour = current.astimezone(timezone.utc).hour

    if hour < 8:
        return "ASIA"

    if hour < 13:
        return "LONDON"

    if hour < 21:
        return "NEW_YORK"

    return "LATE_US"


def build_live_pattern_fingerprint(
    *,
    symbol: str,
    side: str,
    technical: dict | None,
    order_flow: dict | None,
    order_book: dict | None,
    live_regime: dict | None,
    institutional_strategy: dict | None,
    research_confluence: dict | None,
    now: datetime | None = None,
) -> dict:
    """Return the same categorical/numeric shape used by stored experiences."""
    technical = _mapping(technical)
    order_flow = _mapping(order_flow)
    order_book = _mapping(order_book)
    live_regime = _mapping(live_regime)
    institutional_strategy = _mapping(
        institutional_strategy
    )
    research_confluence = _mapping(
        research_confluence
    )

    return {
        "symbol": str(symbol or "").upper(),
        "side": str(side or "HOLD").upper(),
        "session": _session_name(now),
        "market_regime": _directional_text(
            live_regime,
            "regime",
            "market_regime",
        ),
        "strategy": _directional_text(
            institutional_strategy,
            "selected_strategy",
            "strategy",
        ),
        "technical_trend": _directional_text(
            technical,
            "trend",
            "ema_trend",
            "signal",
        ),
        "macd_direction": _directional_text(
            technical,
            "macd_direction",
            "macd_signal",
            "macd",
        ),
        "order_flow_pressure": _directional_text(
            order_flow,
            "pressure",
            "signal",
            "direction",
        ),
        "order_book_pressure": _directional_text(
            order_book,
            "pressure",
            "signal",
            "direction",
        ),
        "research_decision": _directional_text(
            research_confluence,
            "decision",
            "status",
        ),
        "rsi_bucket": round(
            _safe_float(
                technical.get("rsi"),
                50.0,
            )
            / 10.0
        )
        * 10,
        "adx_bucket": round(
            _safe_float(
                technical.get("adx"),
                0.0,
            )
            / 5.0
        )
        * 5,
        "delta_bucket": round(
            _safe_float(
                order_flow.get("delta_ratio"),
                0.0,
            ),
            1,
        ),
    }
