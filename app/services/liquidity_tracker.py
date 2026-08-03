"""
TitanAI Liquidity Tracker v2
Persistent liquidity history for institutional behavior tracking.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

HISTORY_FILE = Path("data/liquidity_history.json")
MAX_HISTORY_PER_SYMBOL = 100


def _load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {}

    with open(HISTORY_FILE, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}


def _save_history(history: dict) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(HISTORY_FILE, "w") as file:
        json.dump(history, file, indent=2)


def record_liquidity(symbol: str, liquidity: dict) -> dict:
    history = _load_history()

    if symbol not in history:
        history[symbol] = []

    history[symbol].append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "bid_liquidity": liquidity.get("bid_liquidity", 0),
        "ask_liquidity": liquidity.get("ask_liquidity", 0),
        "imbalance": liquidity.get("imbalance", 0),
        "pressure": liquidity.get("pressure"),
        "bid_walls": liquidity.get("bid_walls", []),
        "ask_walls": liquidity.get("ask_walls", []),
    })

    history[symbol] = history[symbol][-MAX_HISTORY_PER_SYMBOL:]

    _save_history(history)

    return analyze_liquidity_history(symbol)


def analyze_liquidity_history(symbol: str) -> dict:
    history = _load_history().get(symbol, [])

    if len(history) < 3:
        return {
            "status": "collecting",
            "samples": len(history),
            "signal": "INSUFFICIENT_DATA",
        }

    first = history[0]
    latest = history[-1]

    bid_change_pct = (
        (latest["bid_liquidity"] - first["bid_liquidity"])
        / first["bid_liquidity"] * 100
        if first["bid_liquidity"] else 0
    )

    ask_change_pct = (
        (latest["ask_liquidity"] - first["ask_liquidity"])
        / first["ask_liquidity"] * 100
        if first["ask_liquidity"] else 0
    )

    signal = "NEUTRAL"

    if bid_change_pct > 30 and ask_change_pct < 10:
        signal = "BID_ACCUMULATION"
    elif ask_change_pct > 30 and bid_change_pct < 10:
        signal = "ASK_DISTRIBUTION"
    elif ask_change_pct < -30:
        signal = "ASK_WALL_REMOVED"
    elif bid_change_pct < -30:
        signal = "BID_WALL_REMOVED"

    return {
        "status": "ready",
        "samples": len(history),
        "signal": signal,
        "bid_change_pct": round(bid_change_pct, 2),
        "ask_change_pct": round(ask_change_pct, 2),
        "latest_pressure": latest.get("pressure"),
    }