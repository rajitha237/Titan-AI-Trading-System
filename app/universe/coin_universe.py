"""
TitanAI Coin Universe
"""

CORE_SYMBOLS = [
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
    "DOGEUSDT",
    "ADAUSDT",
    "NEARUSDT",
    "SUIUSDT",
    "BCHUSDT",
    "LINKUSDT",
    "AAVEUSDT",
    "AVAXUSDT",
    "FILUSDT",
    "LTCUSDT",
    "DOTUSDT",
    "UNIUSDT",
    "TRXUSDT",
    "INJUSDT",
    "APTUSDT",
]


def get_trade_universe() -> list[str]:
    return CORE_SYMBOLS