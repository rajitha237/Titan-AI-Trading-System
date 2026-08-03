"""
TitanAI - AI Signal Engine v1
"""

from typing import Dict, Any


def generate_signals(prices: Dict[str, float]) -> Dict[str, Any]:
    """
    Generate simple trading signals from market prices.

    NOTE:
    This is only Version 1.
    Later we will use:
    - Order Book
    - Order Flow
    - Open Interest
    - CVD
    - Funding Rate
    - Liquidations
    - AI Models
    """

    signals = {}

    for symbol, price in prices.items():

        signal = "HOLD"
        confidence = 0.50

        if price > 0:
            signal = "BUY"
            confidence = 0.60

        signals[symbol] = {
            "price": price,
            "signal": signal,
            "confidence": confidence,
        }

    return signals