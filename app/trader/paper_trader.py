"""
TitanAI Paper Trading Engine v1
"""

from datetime import datetime


paper_positions = []


def open_paper_trade(
    symbol: str,
    decision: str,
    price: float,
    risk_plan: dict,
    ai_score: dict,
) -> dict:
    if decision not in ["BUY", "SELL"]:
        return {
            "status": "skipped",
            "reason": "Decision is HOLD",
        }

    trade = {
        "id": len(paper_positions) + 1,
        "symbol": symbol,
        "side": decision,
        "entry_price": price,
        "position_size": risk_plan["position_size"],
        "stop_loss_percent": risk_plan["stop_loss_percent"],
        "take_profit_percent": risk_plan["take_profit_percent"],
        "ai_score": ai_score["score"],
        "status": "OPEN",
        "opened_at": datetime.utcnow().isoformat(),
    }

    paper_positions.append(trade)

    return {
        "status": "opened",
        "trade": trade,
    }


def get_paper_positions() -> list[dict]:
    return paper_positions