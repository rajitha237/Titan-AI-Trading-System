"""
TitanAI Position Manager v3
TP/SL Exit Manager + Memory Outcome Updater
"""

from app.exchange.binance_testnet_client import (
    get_open_positions,
    close_position,
)

from app.memory.memory_updater import update_trade_result
from app.strategy.strategy_store import get_strategy
from app.trader.exit_manager import check_exit_signal


def calculate_position_profit(position: dict) -> float:
    return round(float(position.get("unRealizedProfit", 0)), 4)


def classify_result(profit: float) -> str:
    return "WIN" if profit > 0 else "LOSS"


def manage_open_positions(
    final_decision: dict,
    symbol: str = "BTCUSDT",
) -> dict:
    positions = get_open_positions()
    decision = final_decision.get("decision")

    symbol_positions = [
        position
        for position in positions
        if position["symbol"] == symbol
    ]

    if not symbol_positions:
        return {
            "status": "no_position",
            "message": "No open position to manage",
        }

    position = symbol_positions[0]
    position_amount = float(position["positionAmt"])
    current_side = "BUY" if position_amount > 0 else "SELL"

    strategy = get_strategy(symbol) or {
        "tp": 1.0,
        "sl": 1.0,
        "trailing": 0.3,
        "hold": 40,
    }

    exit_status = check_exit_signal(
        position=position,
        strategy=strategy,
    )

    if exit_status["status"] == "closed":
        profit = calculate_position_profit(position)

        memory_update = update_trade_result(
            symbol=symbol,
            result=classify_result(profit),
            profit=profit,
            holding_minutes=0,
            exit_reason=exit_status["reason"],
        )

        return {
            "status": "closed",
            "reason": exit_status["reason"],
            "side": current_side,
            "profit": profit,
            "memory_update": memory_update,
            "strategy": strategy,
            "exit_status": exit_status,
        }

    if decision in ["BUY", "SELL"] and decision != current_side:
        quantity = abs(position_amount)
        profit = calculate_position_profit(position)

        close_result = close_position(
            symbol=symbol,
            quantity=quantity,
            side=current_side,
        )

        memory_update = update_trade_result(
            symbol=symbol,
            result=classify_result(profit),
            profit=profit,
            holding_minutes=0,
            exit_reason="OPPOSITE_SIGNAL",
        )

        return {
            "status": "closed",
            "reason": "Opposite signal detected",
            "old_side": current_side,
            "new_signal": decision,
            "profit": profit,
            "memory_update": memory_update,
            "close_result": close_result,
        }

    return {
        "status": "holding",
        "side": current_side,
        "position_amount": position_amount,
        "entry_price": position["entryPrice"],
        "mark_price": position["markPrice"],
        "unrealized_profit": position["unRealizedProfit"],
        "strategy": strategy,
        "exit_status": exit_status,
        "message": "Position is being monitored",
    }