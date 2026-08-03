"""
TitanAI Confidence Engine v3
Strategy Store + Pattern Similarity Memory + Safe Fallback
"""

from app.strategy.strategy_store import get_strategy
from app.memory.pattern_similarity import find_similar_setups


DEFAULT_STRATEGY = {
    "tp": 1.0,
    "sl": 1.0,
    "trailing": 0.3,
    "hold": 40,
    "win_rate": 50,
    "total_pnl": 0,
}


def calculate_confidence(symbol: str, ai_score: dict) -> dict:
    strategy = get_strategy(symbol) or DEFAULT_STRATEGY

    confidence = ai_score.get("score", 0)
    reasons = []

    if strategy == DEFAULT_STRATEGY:
        confidence -= 5
        reasons.append("Using fallback strategy")

    pnl = strategy.get("total_pnl", 0) or 0
    win_rate = strategy.get("win_rate", 0) or 0

    if pnl > 20:
        confidence += 10
        reasons.append("Strong historical strategy PnL")
    elif pnl > 10:
        confidence += 7
        reasons.append("Good historical strategy PnL")
    elif pnl > 5:
        confidence += 5
        reasons.append("Positive historical strategy PnL")
    elif pnl > 0:
        confidence += 2
        reasons.append("Slightly positive historical strategy PnL")
    else:
        confidence -= 3
        reasons.append("No positive strategy PnL edge")

    if win_rate >= 70:
        confidence += 8
        reasons.append("Strong historical win rate")
    elif win_rate >= 60:
        confidence += 5
        reasons.append("Good historical win rate")
    elif win_rate >= 50:
        confidence += 2
        reasons.append("Acceptable historical win rate")
    else:
        confidence -= 5
        reasons.append("Weak historical win rate")

    memory = find_similar_setups({
        "symbol": symbol,
        "order_flow_pressure": ai_score.get("order_flow", {}).get("pressure"),
        "quality_score": ai_score.get("score"),
    })

    memory_win_rate = memory.get("win_rate")
    memory_matches = memory.get("matches", 0)

    if memory_win_rate is not None and memory_matches >= 5:
        if memory_win_rate >= 70:
            confidence += 5
            reasons.append("Memory shows strong similar setup performance")
        elif memory_win_rate >= 55:
            confidence += 2
            reasons.append("Memory shows acceptable similar setup performance")
        elif memory_win_rate < 45:
            confidence -= 8
            reasons.append("Memory shows weak similar setup performance")

    confidence = max(0, min(100, confidence))

    if confidence >= 90:
        decision = "TRADE"
    elif confidence >= 75:
        decision = "WATCH"
    else:
        decision = "REJECT"

    return {
        "confidence": confidence,
        "decision": decision,
        "strategy": strategy,
        "memory": {
            "matches": memory_matches,
            "win_rate": memory_win_rate,
        },
        "reasons": reasons,
    }