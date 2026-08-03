"""
TitanAI Memory Outcome Updater v1
"""

import json
from pathlib import Path

MEMORY_FILE = Path("data/market_memory.json")


def update_trade_result(
    symbol: str,
    result: str,
    profit: float,
    holding_minutes: float,
    exit_reason: str,
):
    if not MEMORY_FILE.exists():
        return {
            "status": "no_memory_file",
        }

    with open(MEMORY_FILE, "r") as file:
        memories = json.load(file)

    # newest matching executed trade
    for memory in reversed(memories):

        if (
            memory.get("symbol") == symbol
            and memory.get("executed")
            and memory.get("result") is None
        ):

            memory["result"] = result
            memory["profit"] = profit
            memory["holding_minutes"] = holding_minutes
            memory["exit_reason"] = exit_reason

            with open(MEMORY_FILE, "w") as file:
                json.dump(memories, file, indent=2)

            return {
                "status": "updated",
                "symbol": symbol,
            }

    return {
        "status": "not_found",
    }