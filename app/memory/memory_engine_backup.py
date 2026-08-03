"""
TitanAI AI Memory Engine v1

Stores market context from every cycle so TitanAI can learn patterns later.
"""

import json
from datetime import datetime
from pathlib import Path

MEMORY_FILE = Path("data/market_memory.json")


def build_memory_record(cycle_result: dict) -> dict:
    best_setup = cycle_result.get("best_setup") or {}
    ai_score = best_setup.get("ai_score") or {}
    final_decision = best_setup.get("final_decision") or {}

    confidence = cycle_result.get("confidence") or {}
    trade_quality = cycle_result.get("trade_quality") or {}
    execution = cycle_result.get("execution") or {}

    order_book = best_setup.get("order_book") or {}
    order_flow = best_setup.get("order_flow") or {}
    technical = best_setup.get("technical") or {}
    multi_timeframe = best_setup.get("multi_timeframe") or {}

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": cycle_result.get("symbol"),
        "price": cycle_result.get("price"),
        "ai_score": ai_score.get("score"),
        "ai_signal": ai_score.get("signal"),
        "confidence": confidence.get("confidence"),
        "confidence_decision": confidence.get("decision"),
        "quality_score": trade_quality.get("quality_score"),
        "quality_action": trade_quality.get("action"),
        "final_decision": final_decision.get("decision"),
        "order_book_pressure": order_book.get("pressure"),
        "order_book_imbalance": order_book.get("imbalance"),
        "order_flow_pressure": order_flow.get("pressure"),
        "order_flow_delta_ratio": order_flow.get("delta_ratio"),
        "whale_trade_count": order_flow.get("whale_trade_count"),
        "technical_trend": technical.get("trend"),
        "rsi": technical.get("rsi"),
        "macd_direction": technical.get("macd_direction"),
        "multi_timeframe_trend": multi_timeframe.get("overall_trend"),
        "strategy": cycle_result.get("optimized_strategy"),
        "risk_plan": cycle_result.get("risk_plan"),
        "position_size_usdt": cycle_result.get("position_size_usdt"),
        "quantity": cycle_result.get("quantity"),
        "executed": execution.get("status") == "executed",
        "execution_status": execution.get("status"),
        "result": None,
    }


def save_memory_record(cycle_result: dict) -> dict:
    MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = build_memory_record(cycle_result)

    existing = []

    if MEMORY_FILE.exists():
        with open(MEMORY_FILE, "r") as file:
            try:
                existing = json.load(file)
            except json.JSONDecodeError:
                existing = []

    existing.append(record)

    with open(MEMORY_FILE, "w") as file:
        json.dump(existing, file, indent=2)

    return {
        "status": "saved",
        "file": str(MEMORY_FILE),
        "total_records": len(existing),
    }


def get_memory_records() -> list:
    if not MEMORY_FILE.exists():
        return []

    with open(MEMORY_FILE, "r") as file:
        try:
            return json.load(file)
        except json.JSONDecodeError:
            return []