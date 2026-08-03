"""
TitanAI Strategy Engine v1
"""

def make_trade_decision(ai_score: dict) -> dict:
    score = ai_score.get("score", 50)
    signal = ai_score.get("signal", "HOLD")
    reasons = ai_score.get("reasons", [])

    if score >= 75:
        decision = "BUY"
        risk_level = "MEDIUM"
    elif score <= 35:
        decision = "SELL"
        risk_level = "MEDIUM"
    else:
        decision = "HOLD"
        risk_level = "LOW"

    return {
        "decision": decision,
        "score": score,
        "risk_level": risk_level,
        "reasons": reasons,
        "execute_trade": False,  # Safety: no real trades yet
        "mode": "ANALYSIS_ONLY",
        "source_signal": signal,
    }