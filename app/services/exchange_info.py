import httpx

BINANCE_FUTURES_URL = "https://testnet.binancefuture.com/fapi/v1/exchangeInfo"


async def get_symbol_filters(symbol: str) -> dict:
    symbol = symbol.upper()

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(BINANCE_FUTURES_URL)
        response.raise_for_status()

    data = response.json()

    for item in data["symbols"]:
        if item["symbol"] != symbol:
            continue

        filters = {}

        for f in item["filters"]:
            filters[f["filterType"]] = f

        lot = filters["LOT_SIZE"]
        price = filters["PRICE_FILTER"]
        notional = filters.get("MIN_NOTIONAL")

        return {
            "symbol": symbol,
            "min_qty": float(lot["minQty"]),
            "max_qty": float(lot["maxQty"]),
            "step_size": float(lot["stepSize"]),
            "tick_size": float(price["tickSize"]),
            "min_notional": (
                float(notional["notional"])
                if notional
                else 0.0
            ),
        }

    raise ValueError(f"{symbol} not found")