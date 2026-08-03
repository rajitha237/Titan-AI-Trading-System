"""
TitanAI Order Flow Engine v1

Detects aggressive buyer/seller behavior using Binance recent trades.
"""

import httpx

BINANCE_AGG_TRADES_URL = "https://api.binance.com/api/v3/aggTrades"


async def get_agg_trades(
    symbol: str = "BTCUSDT",
    limit: int = 500,
) -> list:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            BINANCE_AGG_TRADES_URL,
            params={
                "symbol": symbol,
                "limit": limit,
            },
        )
        response.raise_for_status()
        return response.json()


def analyze_order_flow(trades: list) -> dict:
    buy_volume = 0.0
    sell_volume = 0.0
    whale_trades = []

    for trade in trades:
        qty = float(trade["q"])
        price = float(trade["p"])
        value = qty * price

        # m = True means buyer is maker, so aggressive seller
        is_aggressive_sell = trade["m"] is True

        if is_aggressive_sell:
            sell_volume += value
        else:
            buy_volume += value

        if value >= 50_000:
            whale_trades.append({
                "price": price,
                "qty": qty,
                "value": round(value, 2),
                "side": "SELL" if is_aggressive_sell else "BUY",
            })

    total = buy_volume + sell_volume
    delta = buy_volume - sell_volume
    delta_ratio = delta / total if total else 0

    if delta_ratio > 0.15:
        pressure = "AGGRESSIVE_BUYERS"
    elif delta_ratio < -0.15:
        pressure = "AGGRESSIVE_SELLERS"
    else:
        pressure = "BALANCED"

    return {
        "buy_volume": round(buy_volume, 2),
        "sell_volume": round(sell_volume, 2),
        "delta": round(delta, 2),
        "delta_ratio": round(delta_ratio, 4),
        "pressure": pressure,
        "whale_trade_count": len(whale_trades),
        "whale_trades": whale_trades[-10:],
    }


async def get_order_flow_analysis(symbol: str = "BTCUSDT") -> dict:
    trades = await get_agg_trades(symbol)
    return analyze_order_flow(trades)