"""
TitanAI Universe Optimizer

Optimizes every coin in the current trading universe,
ranks the best opportunities, and saves strategy settings.
"""

from app.universe.dynamic_universe import get_dynamic_trade_universe
from app.backtesting.trailing_optimizer import optimize_trailing_strategy
from app.strategy.strategy_store import save_strategy_settings


async def optimize_universe(limit: int = 20):
    symbols = await get_dynamic_trade_universe(limit)

    results = []

    for symbol in symbols:
        try:
            optimization = await optimize_trailing_strategy(symbol)
            best = optimization["best"]

            results.append({
                "symbol": symbol,
                "total_pnl": best["total_pnl"],
                "win_rate": best["win_rate"],
                "tp": best["tp"],
                "sl": best["sl"],
                "trailing": best["trailing"],
                "hold": best["hold"],
            })

            print(f"✓ {symbol} optimized")

        except Exception as e:
            print(f"✗ {symbol}: {e}")

    ranked = sorted(
        results,
        key=lambda x: (
            x["total_pnl"],
            x["win_rate"],
        ),
        reverse=True,
    )

    strategy_settings = {}

    for coin in ranked:
        strategy_settings[coin["symbol"]] = {
            "tp": coin["tp"],
            "sl": coin["sl"],
            "trailing": coin["trailing"],
            "hold": coin["hold"],
            "win_rate": coin["win_rate"],
            "total_pnl": coin["total_pnl"],
        }

    save_result = save_strategy_settings(strategy_settings)

    return {
        "status": "success",
        "tested": len(results),
        "best_coin": ranked[0] if ranked else None,
        "ranking": ranked,
        "saved": len(strategy_settings),
        "save_result": save_result,
    }