"""
TitanAI Trailing Strategy Optimizer
"""

from app.backtesting.backtester import run_simple_backtest


async def optimize_trailing_strategy(
    symbol: str = "BNBUSDT",
    interval: str = "15m",
):
    tp_values = [0.8, 1.0, 1.2, 1.5]
    sl_values = [0.8, 1.0, 1.2]
    trailing_values = [0.3, 0.5, 0.8, 1.0]
    hold_values = [20, 40, 60]

    results = []

    for tp in tp_values:
        for sl in sl_values:
            for trailing in trailing_values:
                for hold in hold_values:
                    result = await run_simple_backtest(
                        symbol=symbol,
                        interval=interval,
                        take_profit_percent=tp,
                        stop_loss_percent=sl,
                        trailing_stop_percent=trailing,
                        max_hold_candles=hold,
                    )

                    results.append({
                        "symbol": symbol,
                        "tp": tp,
                        "sl": sl,
                        "trailing": trailing,
                        "hold": hold,
                        "signals": result["total_signals"],
                        "wins": result["wins"],
                        "losses": result["losses"],
                        "win_rate": result["win_rate"],
                        "total_pnl": result["total_pnl_percent"],
                    })

    ranked = sorted(
        results,
        key=lambda x: (
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