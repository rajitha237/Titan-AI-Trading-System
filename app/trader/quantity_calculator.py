"""
TitanAI Dynamic Quantity Calculator
"""

from app.exchange.binance_testnet_client import format_quantity


def calculate_trade_quantity(
    symbol: str,
    price: float,
    position_size_usdt: float,
) -> float:
    if price <= 0:
        raise ValueError("Price must be greater than zero")

    raw_quantity = position_size_usdt / price
    safe_quantity = format_quantity(symbol, raw_quantity)

    if safe_quantity <= 0:
        raise ValueError(
            f"Calculated quantity is too small for {symbol}: {safe_quantity}"
        )

    return safe_quantity