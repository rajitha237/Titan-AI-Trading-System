"""
TitanAI Strategy Optimizer
"""

from app.backtesting.backtester import run_simple_backtest


async def optimize_strategy(
    symbol: str = "BTCUSDT",
    interval: str = "15m",
):
    tp_values = [0.5, 1.0, 1.5, 2.0, 2.4]
    sl_values = [0.3, 0.5, 0.8, 1.0]
    hold_values = [10, 20, 40]

    results = []

    for tp in tp_values:
        for sl in sl_values:
            for hold in hold_values:

                result = await run_simple_backtest(
                    symbol=symbol,
                    interval=interval,
                    take_profit_percent=tp,
                    stop_loss_percent=sl,
                    max_hold_candles=hold,
                )

                results.append({
                    "tp": tp,
                    "sl": sl,
                    "hold": hold,
                    "win_rate": result["win_rate"],
                    "profit_factor": result["profit_factor"],
                    "total_pnl": result["total_pnl_percent"],
                })

    ranked = sorted(
        results,
        key=lambda x: (
            x["profit_factor"],
            x["total_pnl"],
            x["win_rate"],
        ),
        reverse=True,
    )

    return {
        "status": "success",
        "symbol": symbol,
        "tested": len(results),
        "best": ranked[0],
        "top10": ranked[:10],
    }