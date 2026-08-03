"""Tests for Binance market data service."""

from typing import Any

import httpx
import pytest

from app.services.market_data import (
    DEFAULT_SYMBOLS,
    MarketDataError,
    get_prices,
)


@pytest.fixture
def mock_binance_transport() -> httpx.MockTransport:
    """Return a mock transport that simulates Binance ticker/price responses."""

    def handler(request: httpx.Request) -> httpx.Response:
        symbol = request.url.params.get("symbol")
        if symbol not in DEFAULT_SYMBOLS:
            return httpx.Response(400, json={"code": -1121, "msg": "Invalid symbol."})

        prices: dict[str, str] = {
            "BTCUSDT": "95000.00",
            "ETHUSDT": "3500.00",
            "SOLUSDT": "150.00",
            "XRPUSDT": "0.55",
        }
        return httpx.Response(
            200,
            json={"symbol": symbol, "price": prices[symbol]},
        )

    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_get_prices_returns_expected_dictionary(
    mock_binance_transport: httpx.MockTransport,
) -> None:
    async with httpx.AsyncClient(transport=mock_binance_transport) as client:
        prices = await get_prices(client=client, base_url="https://api.binance.com")

    assert prices == {
        "BTCUSDT": "95000.00",
        "ETHUSDT": "3500.00",
        "SOLUSDT": "150.00",
        "XRPUSDT": "0.55",
    }


@pytest.mark.asyncio
async def test_get_prices_raises_on_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(MarketDataError, match="HTTP 503"):
            await get_prices(symbols=("BTCUSDT",), client=client)


@pytest.mark.asyncio
async def test_get_prices_raises_on_invalid_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload: dict[str, Any] = {"symbol": "BTCUSDT"}
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(MarketDataError, match="Missing price"):
            await get_prices(symbols=("BTCUSDT",), client=client)
