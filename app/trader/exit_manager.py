"""
TitanAI Bot-side Exit Manager v2
Precision-safe TP/SL display and close logic.
"""

from app.exchange.binance_testnet_client import close_position


def get_display_precision(price: float) -> int:
    if price >= 100:
        return 2
    if price >= 1:
        return 4
    if price >= 0.1:
        return 6
    return 8


def check_exit_signal(
    position: dict,
    strategy: dict,
) -> dict:
    symbol = position["symbol"]
    amount = float(position["positionAmt"])
    entry = float(position["entryPrice"])
    mark = float(position["markPrice"])

    side = "BUY" if amount > 0 else "SELL"
    quantity = abs(amount)

    tp_percent = float(strategy["tp"])
    sl_percent = float(strategy["sl"])

    precision = get_display_precision(entry)

    if side == "BUY":
        tp_price = entry * (1 + tp_percent / 100)
        sl_price = entry * (1 - sl_percent / 100)

        if mark >= tp_price:
            close = close_position(symbol=symbol, quantity=quantity, side=side)
            return {"status": "closed", "reason": "TP hit", "close": close}

        if mark <= sl_price:
            close = close_position(symbol=symbol, quantity=quantity, side=side)
            return {"status": "closed", "reason": "SL hit", "close": close}

    else:
        tp_price = entry * (1 - tp_percent / 100)
        sl_price = entry * (1 + sl_percent / 100)

        if mark <= tp_price:
            close = close_position(symbol=symbol, quantity=quantity, side=side)
            return {"status": "closed", "reason": "TP hit", "close": close}

        if mark >= sl_price:
            close = close_position(symbol=symbol, quantity=quantity, side=side)
            return {"status": "closed", "reason": "SL hit", "close": close}

    return {
        "status": "holding",
        "symbol": symbol,
        "side": side,
        "entry": entry,
        "mark": mark,
        "tp_price": round(tp_price, precision),
        "sl_price": round(sl_price, precision),
        "tp_percent": tp_percent,
        "sl_percent": sl_percent,
    }