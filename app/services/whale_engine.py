"""
TitanAI Whale Accumulation / Distribution Engine v2
Persistent rolling whale memory with sample reliability.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.order_flow import get_agg_trades

WHALE_HISTORY_FILE = Path("data/whale_history.json")

MAX_HISTORY_PER_SYMBOL = 60
WHALE_VALUE_USDT = 50_000
MIN_RELIABLE_SAMPLES = 5


def _load_history() -> dict:
    if not WHALE_HISTORY_FILE.exists():
        return {}

    with open(WHALE_HISTORY_FILE, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return {}


def _save_history(history: dict) -> None:
    WHALE_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(WHALE_HISTORY_FILE, "w") as file:
        json.dump(history, file, indent=2)


def _reliability(samples: int) -> str:
    if samples < 5:
        return "COLLECTING"
    if samples < 20:
        return "SHORT_TERM"
    if samples < 50:
        return "RELIABLE"
    return "STRONG"


async def analyze_whale_activity(symbol: str) -> dict:
    trades = await get_agg_trades(symbol, limit=500)

    whale_buy_value = 0.0
    whale_sell_value = 0.0
    whale_buy_count = 0
    whale_sell_count = 0

    for trade in trades:
        qty = float(trade["q"])
        price = float(trade["p"])
        value = qty * price

        if value < WHALE_VALUE_USDT:
            continue

        is_aggressive_sell = trade["m"] is True

        if is_aggressive_sell:
            whale_sell_value += value
            whale_sell_count += 1
        else:
            whale_buy_value += value
            whale_buy_count += 1

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "buy_value": round(whale_buy_value, 2),
        "sell_value": round(whale_sell_value, 2),
        "buy_count": whale_buy_count,
        "sell_count": whale_sell_count,
    }

    history = _load_history()

    if symbol not in history:
        history[symbol] = []

    history[symbol].append(snapshot)
    history[symbol] = history[symbol][-MAX_HISTORY_PER_SYMBOL:]

    _save_history(history)

    symbol_history = history[symbol]
    samples = len(symbol_history)

    total_buy = sum(item.get("buy_value", 0) for item in symbol_history)
    total_sell = sum(item.get("sell_value", 0) for item in symbol_history)

    total = total_buy + total_sell
    whale_delta = total_buy - total_sell
    whale_delta_ratio = whale_delta / total if total else 0

    reliability = _reliability(samples)

    if samples < MIN_RELIABLE_SAMPLES:
        state = "COLLECTING"
        strength = 0
    elif whale_delta_ratio > 0.25 and total_buy > 0:
        state = "ACCUMULATION"
        strength = min(100, abs(whale_delta_ratio) * 100)
    elif whale_delta_ratio < -0.25 and total_sell > 0:
        state = "DISTRIBUTION"
        strength = min(100, abs(whale_delta_ratio) * 100)
    else:
        state = "NEUTRAL"
        strength = min(100, abs(whale_delta_ratio) * 100)

    return {
        "symbol": symbol,
        "state": state,
        "reliability": reliability,
        "strength": round(strength, 2),
        "delta_ratio": round(whale_delta_ratio, 4),
        "total_buy_value": round(total_buy, 2),
        "total_sell_value": round(total_sell, 2),
        "samples": samples,
        "latest": snapshot,
    }