"""
TitanAI Historical Backtesting Engine v7
EMA200 + ADX + trailing exit
"""

import pandas as pd
import ta

from app.services.candles import get_klines, normalize_klines


def build_indicator_dataframe(candles: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(candles)

    df["ema20"] = ta.trend.EMAIndicator(close=df["close"], window=20).ema_indicator()
    df["ema50"] = ta.trend.EMAIndicator(close=df["close"], window=50).ema_indicator()
    df["ema200"] = ta.trend.EMAIndicator(close=df["close"], window=200).ema_indicator()
    df["rsi"] = ta.momentum.RSIIndicator(close=df["close"], window=14).rsi()

    macd = ta.trend.MACD(close=df["close"])
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()

    adx = ta.trend.ADXIndicator(
        high=df["high"],
        low=df["low"],
        close=df["close"],
        window=14,
    )
    df["adx"] = adx.adx()

    return df


def calculate_historical_score(row) -> dict:
    score = 50
    reasons = []

    if row["ema20"] > row["ema50"]:
        score += 15
        reasons.append("EMA20 above EMA50")
    else:
        score -= 15
        reasons.append("EMA20 below EMA50")

    if row["close"] > row["ema200"]:
        score += 15
        reasons.append("Price above EMA200")
    else:
        score -= 15
        reasons.append("Price below EMA200")

    if 45 <= row["rsi"] <= 65:
        score += 10
        reasons.append("RSI healthy")
    elif row["rsi"] > 70:
        score -= 10
        reasons.append("RSI overbought")
    elif row["rsi"] < 30:
        score += 5
        reasons.append("RSI oversold")

    if row["macd"] > row["macd_signal"]:
        score += 15
        reasons.append("MACD buy")
    else:
        score -= 15
        reasons.append("MACD sell")

    if row["adx"] >= 20:
        score += 10
        reasons.append("ADX trend strength confirmed")
    else:
        score -= 10
        reasons.append("ADX weak trend")

    score = max(0, min(100, score))

    return {
        "score": score,
        "signal": "BUY" if score >= 80 else "HOLD",
        "reasons": reasons,
    }


def is_market_structure_valid(row) -> bool:
    return (
        row["ema20"] > row["ema50"]
        and row["close"] > row["ema200"]
        and 45 <= row["rsi"] <= 65
        and row["macd"] > row["macd_signal"]
        and row["adx"] >= 20
    )


async def run_simple_backtest(
    symbol: str = "BTCUSDT",
    interval: str = "15m",
    limit: int = 700,
    min_score: int = 80,
    take_profit_percent: float = 1.0,
    stop_loss_percent: float = 1.0,
    max_hold_candles: int = 40,
    trailing_stop_percent: float = 0.5,
    fee_percent: float = 0.04,
) -> dict:
    raw = await get_klines(symbol, interval, limit)
    candles = normalize_klines(raw)
    df = build_indicator_dataframe(candles)

    trades = []
    wins = 0
    losses = 0
    trailing_exits = 0
    no_exit = 0
    total_pnl_percent = 0.0

    for i in range(220, len(df) - max_hold_candles):
        row = df.iloc[i]
        ai_score = calculate_historical_score(row)

        if ai_score["score"] < min_score:
            continue

        if not is_market_structure_valid(row):
            continue

        entry = float(row["close"])
        entry_time = int(row["time"])

        take_profit = entry * (1 + take_profit_percent / 100)
        stop_loss = entry * (1 - stop_loss_percent / 100)

        highest_price = entry
        trailing_active = False
        trailing_stop = stop_loss

        result = "NO_EXIT"
        exit_price = float(df.iloc[i + max_hold_candles]["close"])
        exit_time = int(df.iloc[i + max_hold_candles]["time"])
        pnl_percent = ((exit_price - entry) / entry) * 100

        for j in range(i + 1, i + max_hold_candles + 1):
            future = df.iloc[j]
            high = float(future["high"])
            low = float(future["low"])

            if high > highest_price:
                highest_price = high

            if high >= take_profit:
                trailing_active = True
                trailing_stop = highest_price * (1 - trailing_stop_percent / 100)

            if trailing_active:
                new_trailing_stop = highest_price * (1 - trailing_stop_percent / 100)
                trailing_stop = max(trailing_stop, new_trailing_stop)

                if low <= trailing_stop:
                    result = "TRAILING_EXIT"
                    exit_price = trailing_stop
                    exit_time = int(future["time"])
                    pnl_percent = ((exit_price - entry) / entry) * 100
                    trailing_exits += 1
                    break

            if not trailing_active and low <= stop_loss:
                result = "LOSS"
                exit_price = stop_loss
                exit_time = int(future["time"])
                pnl_percent = -stop_loss_percent
                losses += 1
                break

        if result == "NO_EXIT":
            no_exit += 1

            if pnl_percent > 0:
                wins += 1
                result = "TIME_EXIT_WIN"
            else:
                losses += 1
                result = "TIME_EXIT_LOSS"

        if result == "TRAILING_EXIT" and pnl_percent > 0:
            wins += 1
        elif result == "TRAILING_EXIT":
            losses += 1

        pnl_after_fees = pnl_percent - (fee_percent * 2)
        total_pnl_percent += pnl_after_fees

        trades.append({
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry": round(entry, 4),
            "exit": round(exit_price, 4),
            "score": ai_score["score"],
            "result": result,
            "pnl_percent": round(pnl_after_fees, 4),
            "reasons": ai_score["reasons"],
        })

    total_closed = wins + losses
    win_rate = (wins / total_closed * 100) if total_closed else 0

    return {
        "status": "success",
        "symbol": symbol,
        "interval": interval,
        "min_score": min_score,
        "total_signals": len(trades),
        "wins": wins,
        "losses": losses,
        "trailing_exits": trailing_exits,
        "time_exits": no_exit,
        "win_rate": round(win_rate, 2),
        "total_pnl_percent": round(total_pnl_percent, 2),
        "take_profit_percent": take_profit_percent,
        "stop_loss_percent": stop_loss_percent,
        "trailing_stop_percent": trailing_stop_percent,
        "max_hold_candles": max_hold_candles,
        "fee_percent": fee_percent,
        "sample_trades": trades[-10:],
    }