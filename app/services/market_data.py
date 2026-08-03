"""Binance public market data service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BINANCE_API_BASE_URL = "https://api.binance.com"
TICKER_PRICE_PATH = "/api/v3/ticker/price"
DEFAULT_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT")
DEFAULT_TIMEOUT_SECONDS = 10.0


class MarketDataError(Exception):
    """Raised when market data cannot be retrieved from Binance."""


async def _fetch_symbol_price(
    client: httpx.AsyncClient,
    symbol: str,
    *,
    base_url: str,
) -> tuple[str, float]:
    """Fetch the latest price for a single trading pair."""
    url = f"{base_url.rstrip('/')}{TICKER_PRICE_PATH}"
    logger.debug("Fetching Binance price for %s", symbol)

    try:
        response = await client.get(url, params={"symbol": symbol})
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.error("Binance request timed out for %s", symbol)
        raise MarketDataError(f"Request timed out for {symbol}") from exc
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Binance HTTP error for %s: status=%s body=%s",
            symbol,
            exc.response.status_code,
            exc.response.text,
        )
        raise MarketDataError(
            f"Binance returned HTTP {exc.response.status_code} for {symbol}"
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("Binance request failed for %s: %s", symbol, exc)
        raise MarketDataError(f"Failed to fetch price for {symbol}") from exc

    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        logger.error("Invalid JSON response for %s: %s", symbol, response.text)
        raise MarketDataError(f"Invalid JSON response for {symbol}") from exc

    if payload.get("symbol") != symbol:
        logger.error("Unexpected symbol in response for %s: %s", symbol, payload)
        raise MarketDataError(f"Unexpected response payload for {symbol}")

    price = payload.get("price")
    if not isinstance(price, str) or not price:
        logger.error("Missing or invalid price for %s: %s", symbol, payload)
        raise MarketDataError(f"Missing price in response for {symbol}")

    logger.debug("Fetched %s price=%s", symbol, price)
    return symbol, float(price)


async def get_prices(
    symbols: tuple[str, ...] | list[str] | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    base_url: str = BINANCE_API_BASE_URL,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, float]:
    """
    Fetch current prices from the Binance public REST API.

    Args:
        symbols: Trading pairs to fetch. Defaults to BTC, ETH, SOL, and XRP vs USDT.
        client: Optional shared httpx client for connection reuse.
        base_url: Binance API base URL.
        timeout: Request timeout in seconds.

    Returns:
        Dictionary mapping symbol to price float, e.g. {"BTCUSDT": 95000.00}.

    Raises:
        MarketDataError: If any price request fails or the response is invalid.
    """
    target_symbols = tuple(symbols) if symbols is not None else DEFAULT_SYMBOLS
    if not target_symbols:
        raise MarketDataError("At least one symbol is required")

    logger.info("Fetching Binance prices for symbols: %s", ", ".join(target_symbols))

    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        headers={"Accept": "application/json"},
    )

    try:
        results = await asyncio.gather(
            *(
                _fetch_symbol_price(http_client, symbol, base_url=base_url)
                for symbol in target_symbols
            )
        )
    finally:
        if owns_client:
            await http_client.aclose()

    prices = dict(results)
    logger.info("Successfully fetched %d Binance prices", len(prices))
    return prices
