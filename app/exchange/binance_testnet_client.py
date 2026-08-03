"""Reliable Binance USD-M Futures Testnet REST client v25.

This module preserves the public function interface used by TitanAI while
adding automatic Binance server-time synchronisation, timestamp-error retry,
connection reuse, safer request handling, and consistent REST behaviour.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import threading
import time
from decimal import Decimal, ROUND_DOWN
from typing import Any
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

BINANCE_TESTNET_BASE_URL = os.getenv(
    "BINANCE_TESTNET_BASE_URL",
    "https://testnet.binancefuture.com",
).rstrip("/")
DEFAULT_RECV_WINDOW = int(os.getenv("BINANCE_RECV_WINDOW", "10000"))
DEFAULT_HTTP_TIMEOUT = float(os.getenv("BINANCE_HTTP_TIMEOUT", "15"))
DEFAULT_MAX_RETRIES = int(os.getenv("BINANCE_MAX_RETRIES", "2"))
TIME_SYNC_TTL_SECONDS = float(os.getenv("BINANCE_TIME_SYNC_TTL", "300"))

API_KEY = os.getenv("BINANCE_TESTNET_API_KEY")
API_SECRET = os.getenv("BINANCE_TESTNET_API_SECRET")

if not API_KEY:
    raise RuntimeError("BINANCE_TESTNET_API_KEY is missing from environment")
if not API_SECRET:
    raise RuntimeError("BINANCE_TESTNET_API_SECRET is missing from environment")

_SESSION = requests.Session()
_SESSION.headers.update({"X-MBX-APIKEY": API_KEY})

_TIME_OFFSET_MS = 0
_LAST_TIME_SYNC_MONOTONIC = 0.0
_TIME_LOCK = threading.Lock()


class BinanceAPIError(RuntimeError):
    """Raised when Binance returns an unsuccessful API response."""

    def __init__(
        self,
        code: int | str,
        message: str,
        *,
        status_code: int | None = None,
        response_data: Any = None,
    ) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(f"Binance API error {code}: {message}")


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        raise ValueError("Symbol is required")
    return normalized


def _normalize_side(side: str) -> str:
    normalized = str(side or "").strip().upper()
    if normalized not in {"BUY", "SELL"}:
        raise ValueError("Side must be BUY or SELL")
    return normalized


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_api_string(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _remove_empty_parameters(parameters: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in parameters.items()
        if value is not None and value != ""
    }


def _decode_response(response: requests.Response) -> Any:
    try:
        data = response.json()
    except ValueError:
        data = {"code": response.status_code, "msg": response.text}

    if response.ok:
        return data

    if isinstance(data, dict):
        code = data.get("code", response.status_code)
        message = str(data.get("msg", response.text))
    else:
        code = response.status_code
        message = str(data)

    raise BinanceAPIError(
        code,
        message,
        status_code=response.status_code,
        response_data=data,
    )


def _public_request(
    method: str,
    path: str,
    parameters: dict[str, Any] | None = None,
) -> Any:
    url = f"{BINANCE_TESTNET_BASE_URL}{path}"
    params = _remove_empty_parameters(dict(parameters or {}))

    try:
        response = _SESSION.request(
            method=method.upper(),
            url=url,
            params=params,
            timeout=DEFAULT_HTTP_TIMEOUT,
        )
    except requests.RequestException as error:
        raise RuntimeError(
            f"Binance network error for {method.upper()} {path}: {error}"
        ) from error

    return _decode_response(response)


def get_server_time() -> int:
    """Return Binance Futures server time in milliseconds."""
    result = _public_request("GET", "/fapi/v1/time")
    try:
        return int(result["serverTime"])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"Invalid Binance server-time response: {result!r}") from error


def sync_server_time(force: bool = False) -> int:
    """Synchronise and cache the local-to-Binance clock offset.

    A midpoint estimate reduces network-latency bias. The returned value is the
    signed-request offset in milliseconds.
    """
    global _TIME_OFFSET_MS, _LAST_TIME_SYNC_MONOTONIC

    with _TIME_LOCK:
        age = time.monotonic() - _LAST_TIME_SYNC_MONOTONIC
        if not force and _LAST_TIME_SYNC_MONOTONIC and age < TIME_SYNC_TTL_SECONDS:
            return _TIME_OFFSET_MS

        local_before = time.time_ns() // 1_000_000
        server_time = get_server_time()
        local_after = time.time_ns() // 1_000_000
        local_midpoint = (local_before + local_after) // 2

        _TIME_OFFSET_MS = server_time - local_midpoint
        _LAST_TIME_SYNC_MONOTONIC = time.monotonic()
        return _TIME_OFFSET_MS


def get_time_sync_status() -> dict[str, Any]:
    """Return diagnostic information about cached server-time synchronisation."""
    age = (
        None
        if not _LAST_TIME_SYNC_MONOTONIC
        else max(0.0, time.monotonic() - _LAST_TIME_SYNC_MONOTONIC)
    )
    return {
        "offset_ms": _TIME_OFFSET_MS,
        "last_sync_age_seconds": age,
        "sync_ttl_seconds": TIME_SYNC_TTL_SECONDS,
        "recv_window": DEFAULT_RECV_WINDOW,
    }


def _current_timestamp_ms() -> int:
    if (
        not _LAST_TIME_SYNC_MONOTONIC
        or time.monotonic() - _LAST_TIME_SYNC_MONOTONIC >= TIME_SYNC_TTL_SECONDS
    ):
        sync_server_time()
    return (time.time_ns() // 1_000_000) + _TIME_OFFSET_MS


def _build_signed_parameters(parameters: dict[str, Any]) -> dict[str, str]:
    params = dict(parameters)
    params["timestamp"] = _current_timestamp_ms()
    params.setdefault("recvWindow", DEFAULT_RECV_WINDOW)
    params = _remove_empty_parameters(params)

    serializable = {key: _to_api_string(value) for key, value in params.items()}
    query_string = urlencode(serializable)
    signature = hmac.new(
        API_SECRET.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return {**serializable, "signature": signature}


def _signed_request(
    method: str,
    path: str,
    parameters: dict[str, Any] | None = None,
    *,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Any:
    """Send an authenticated request and retry timestamp failures automatically."""
    url = f"{BINANCE_TESTNET_BASE_URL}{path}"
    method = method.upper()
    base_params = dict(parameters or {})
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        signed_params = _build_signed_parameters(base_params)

        request_kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "timeout": DEFAULT_HTTP_TIMEOUT,
        }
        if method in {"POST", "PUT"}:
            request_kwargs["data"] = signed_params
            request_kwargs["headers"] = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
        elif method in {"GET", "DELETE"}:
            request_kwargs["params"] = signed_params
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        try:
            response = _SESSION.request(**request_kwargs)
            return _decode_response(response)
        except BinanceAPIError as error:
            last_error = error
            if str(error.code) == "-1021" and attempt < max_retries:
                sync_server_time(force=True)
                continue
            raise
        except requests.RequestException as error:
            last_error = error
            if attempt < max_retries:
                time.sleep(min(0.25 * (2**attempt), 1.0))
                continue
            raise RuntimeError(
                f"Binance network error for {method} {path}: {error}"
            ) from error

    raise RuntimeError(f"Binance request failed: {last_error}")


def get_account_balance() -> dict | None:
    balances = _signed_request("GET", "/fapi/v2/balance")
    if not isinstance(balances, list):
        raise RuntimeError(f"Invalid Binance balance response: {balances!r}")
    return next(
        (item for item in balances if item.get("asset") == "USDT"),
        None,
    )


def get_exchange_info() -> dict:
    result = _public_request("GET", "/fapi/v1/exchangeInfo")
    if not isinstance(result, dict):
        raise RuntimeError(f"Invalid Binance exchange-info response: {result!r}")
    return result


def get_symbol_info(symbol: str) -> dict:
    normalized_symbol = _normalize_symbol(symbol)
    exchange_info = get_exchange_info()
    symbol_info = next(
        (
            item
            for item in exchange_info.get("symbols", [])
            if item.get("symbol") == normalized_symbol
        ),
        None,
    )
    if symbol_info is None:
        raise ValueError(
            f"Symbol not found in Binance exchange info: {normalized_symbol}"
        )
    return symbol_info


def get_symbol_quantity_precision(symbol: str) -> int:
    return int(get_symbol_info(symbol).get("quantityPrecision", 0))


def get_symbol_price_precision(symbol: str) -> int:
    return int(get_symbol_info(symbol).get("pricePrecision", 0))


def _get_symbol_filter(symbol: str, filter_type: str) -> dict | None:
    return next(
        (
            item
            for item in get_symbol_info(symbol).get("filters", [])
            if item.get("filterType") == filter_type
        ),
        None,
    )


def get_quantity_step_size(symbol: str) -> Decimal:
    lot_filter = _get_symbol_filter(symbol, "MARKET_LOT_SIZE")
    if not lot_filter:
        lot_filter = _get_symbol_filter(symbol, "LOT_SIZE")
    if not lot_filter:
        return Decimal("1").scaleb(-get_symbol_quantity_precision(symbol))
    return Decimal(str(lot_filter.get("stepSize", "1")))


def get_price_tick_size(symbol: str) -> Decimal:
    price_filter = _get_symbol_filter(symbol, "PRICE_FILTER")
    if not price_filter:
        return Decimal("1").scaleb(-get_symbol_price_precision(symbol))
    return Decimal(str(price_filter.get("tickSize", "1")))


def _round_down_to_step(value: float, step: Decimal) -> Decimal:
    decimal_value = Decimal(str(value))
    if decimal_value <= 0:
        return Decimal("0")
    if step <= 0:
        return decimal_value
    steps = (decimal_value / step).to_integral_value(rounding=ROUND_DOWN)
    return steps * step


def format_quantity(symbol: str, quantity: float) -> float:
    normalized_symbol = _normalize_symbol(symbol)
    formatted = _round_down_to_step(
        quantity,
        get_quantity_step_size(normalized_symbol),
    )
    if formatted <= 0:
        raise ValueError(
            f"Formatted quantity for {normalized_symbol} must be greater than zero"
        )
    return float(formatted)


def format_price(symbol: str, price: float) -> float:
    normalized_symbol = _normalize_symbol(symbol)
    formatted = _round_down_to_step(
        price,
        get_price_tick_size(normalized_symbol),
    )
    if formatted <= 0:
        raise ValueError(
            f"Formatted price for {normalized_symbol} must be greater than zero"
        )
    return float(formatted)


def place_test_market_order(
    symbol: str = "BTCUSDT",
    side: str = "BUY",
    quantity: float = 0.001,
) -> dict:
    normalized_symbol = _normalize_symbol(symbol)
    result = _signed_request(
        "POST",
        "/fapi/v1/order",
        {
            "symbol": normalized_symbol,
            "side": _normalize_side(side),
            "type": "MARKET",
            "quantity": format_quantity(normalized_symbol, quantity),
            "newOrderRespType": "RESULT",
        },
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"Invalid Binance order response: {result!r}")
    return result


def get_open_positions(symbol: str | None = None) -> list:
    params: dict[str, Any] = {}
    if symbol:
        params["symbol"] = _normalize_symbol(symbol)
    positions = _signed_request("GET", "/fapi/v2/positionRisk", params)
    if not isinstance(positions, list):
        raise RuntimeError(f"Invalid Binance position response: {positions!r}")
    return [
        position
        for position in positions
        if _safe_float(position.get("positionAmt"), 0.0) != 0
    ]


def get_normal_open_orders(symbol: str | None = None) -> list:
    params: dict[str, Any] = {}
    if symbol:
        params["symbol"] = _normalize_symbol(symbol)
    orders = _signed_request("GET", "/fapi/v1/openOrders", params)
    return orders if isinstance(orders, list) else []


def _normalize_algo_order(order: dict) -> dict:
    normalized = dict(order)
    normalized["orderId"] = order.get("algoId")
    normalized["clientOrderId"] = order.get("clientAlgoId")
    normalized["type"] = order.get("orderType", order.get("type"))
    normalized["status"] = order.get("algoStatus", order.get("status", "NEW"))
    normalized["stopPrice"] = order.get(
        "triggerPrice", order.get("stopPrice", "0")
    )
    normalized["origQty"] = order.get("quantity", order.get("origQty", "0"))
    normalized["price"] = order.get("price", "0")
    normalized["reduceOnly"] = bool(order.get("reduceOnly", False))
    normalized["workingType"] = order.get("workingType")
    normalized["isAlgoOrder"] = True
    return normalized


def get_open_algo_orders(symbol: str | None = None) -> list:
    params: dict[str, Any] = {"algoType": "CONDITIONAL"}
    if symbol:
        params["symbol"] = _normalize_symbol(symbol)
    result = _signed_request("GET", "/fapi/v1/openAlgoOrders", params)
    if not isinstance(result, list):
        return []
    return [
        _normalize_algo_order(order)
        for order in result
        if isinstance(order, dict)
    ]


def get_open_orders(symbol: str | None = None) -> list:
    return [
        *get_normal_open_orders(symbol=symbol),
        *get_open_algo_orders(symbol=symbol),
    ]


def cancel_normal_open_orders(symbol: str) -> dict:
    normalized_symbol = _normalize_symbol(symbol)
    result = _signed_request(
        "DELETE",
        "/fapi/v1/allOpenOrders",
        {"symbol": normalized_symbol},
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"Invalid cancel-all response: {result!r}")
    return result


def cancel_algo_open_orders(symbol: str) -> dict:
    normalized_symbol = _normalize_symbol(symbol)
    result = _signed_request(
        "DELETE",
        "/fapi/v1/algoOpenOrders",
        {"symbol": normalized_symbol},
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"Invalid algo cancel-all response: {result!r}")
    return result


def cancel_algo_order(symbol: str, order_id: int | str) -> dict:
    """Cancel one conditional algo order without touching other protection."""
    normalized_symbol = _normalize_symbol(symbol)
    if order_id in (None, ""):
        raise ValueError("Algo order ID is required")
    result = _signed_request(
        "DELETE",
        "/fapi/v1/algoOrder",
        {"symbol": normalized_symbol, "algoId": order_id},
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"Invalid algo cancellation response: {result!r}")
    return result


def cancel_open_orders(symbol: str = "BTCUSDT") -> dict:
    normalized_symbol = _normalize_symbol(symbol)
    normal_result = algo_result = None
    normal_error = algo_error = None

    try:
        normal_result = cancel_normal_open_orders(normalized_symbol)
    except Exception as error:  # Keep partial cancellation diagnostics.
        normal_error = str(error)

    try:
        algo_result = cancel_algo_open_orders(normalized_symbol)
    except Exception as error:
        algo_error = str(error)

    if normal_error and algo_error:
        raise RuntimeError(
            "Could not cancel normal or algo orders. "
            f"Normal error: {normal_error}. Algo error: {algo_error}"
        )

    return {
        "symbol": normalized_symbol,
        "normal_orders": {
            "success": normal_error is None,
            "result": normal_result,
            "error": normal_error,
        },
        "algo_orders": {
            "success": algo_error is None,
            "result": algo_result,
            "error": algo_error,
        },
    }


def _place_conditional_algo_order(
    symbol: str,
    close_side: str,
    order_type: str,
    trigger_price: float,
    quantity: float,
) -> dict:
    normalized_symbol = _normalize_symbol(symbol)
    result = _signed_request(
        "POST",
        "/fapi/v1/algoOrder",
        {
            "algoType": "CONDITIONAL",
            "symbol": normalized_symbol,
            "side": _normalize_side(close_side),
            "positionSide": "BOTH",
            "type": order_type,
            "quantity": format_quantity(normalized_symbol, quantity),
            "triggerPrice": format_price(normalized_symbol, trigger_price),
            "workingType": "MARK_PRICE",
            "reduceOnly": "true",
            "priceProtect": "false",
            "newOrderRespType": "RESULT",
        },
    )
    if not isinstance(result, dict):
        raise RuntimeError("Binance returned an invalid algo order response")
    return _normalize_algo_order(result)


def place_stop_loss_order(
    symbol: str,
    side: str,
    stop_price: float,
    quantity: float,
) -> dict:
    position_side = _normalize_side(side)
    close_side = "SELL" if position_side == "BUY" else "BUY"
    return _place_conditional_algo_order(
        symbol=symbol,
        close_side=close_side,
        order_type="STOP_MARKET",
        trigger_price=stop_price,
        quantity=quantity,
    )


def place_take_profit_order(
    symbol: str,
    side: str,
    take_profit_price: float,
    quantity: float,
) -> dict:
    position_side = _normalize_side(side)
    close_side = "SELL" if position_side == "BUY" else "BUY"
    return _place_conditional_algo_order(
        symbol=symbol,
        close_side=close_side,
        order_type="TAKE_PROFIT_MARKET",
        trigger_price=take_profit_price,
        quantity=quantity,
    )


def close_position(
    symbol: str = "BTCUSDT",
    quantity: float = 0.001,
    side: str = "BUY",
) -> dict:
    normalized_symbol = _normalize_symbol(symbol)
    position_side = _normalize_side(side)
    close_side = "SELL" if position_side == "BUY" else "BUY"
    result = _signed_request(
        "POST",
        "/fapi/v1/order",
        {
            "symbol": normalized_symbol,
            "side": close_side,
            "type": "MARKET",
            "quantity": format_quantity(normalized_symbol, quantity),
            "reduceOnly": "true",
            "newOrderRespType": "RESULT",
        },
    )
    if not isinstance(result, dict):
        raise RuntimeError(f"Invalid close-position response: {result!r}")
    return result


def get_user_trades(
    symbol: str,
    *,
    start_time: int | None = None,
    end_time: int | None = None,
    from_id: int | None = None,
    limit: int = 1000,
) -> list:
    """Return exact USD-M Futures account trades for one symbol."""
    params: dict[str, Any] = {
        "symbol": _normalize_symbol(symbol),
        "limit": max(1, min(int(limit), 1000)),
    }
    if start_time is not None:
        params["startTime"] = int(start_time)
    if end_time is not None:
        params["endTime"] = int(end_time)
    if from_id is not None:
        params["fromId"] = int(from_id)

    result = _signed_request("GET", "/fapi/v1/userTrades", params)
    if not isinstance(result, list):
        raise RuntimeError(f"Invalid Binance user-trades response: {result!r}")
    return [item for item in result if isinstance(item, dict)]


def get_income_history(
    *,
    symbol: str | None = None,
    income_type: str | None = None,
    start_time: int | None = None,
    end_time: int | None = None,
    limit: int = 1000,
) -> list:
    """Return Binance Futures income records for realized-PnL auditing."""
    params: dict[str, Any] = {
        "limit": max(1, min(int(limit), 1000)),
    }
    if symbol:
        params["symbol"] = _normalize_symbol(symbol)
    if income_type:
        params["incomeType"] = str(income_type).upper()
    if start_time is not None:
        params["startTime"] = int(start_time)
    if end_time is not None:
        params["endTime"] = int(end_time)

    result = _signed_request("GET", "/fapi/v1/income", params)
    if not isinstance(result, list):
        raise RuntimeError(f"Invalid Binance income-history response: {result!r}")
    return [item for item in result if isinstance(item, dict)]


class BinanceClientCompatibilityFacade:
    """Backward-compatible client object for legacy TitanAI modules.

    Older modules import ``client`` and call methods from Binance's UMFutures
    SDK. This facade preserves the method names while routing every signed
    request through TitanAI's time-synchronised REST layer.
    """

    def balance(self, **params: Any) -> list:
        result = _signed_request("GET", "/fapi/v2/balance", params)
        return result if isinstance(result, list) else []

    def account(self, **params: Any) -> dict:
        result = _signed_request("GET", "/fapi/v2/account", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance account response: {result!r}")
        return result

    def exchange_info(self, **params: Any) -> dict:
        result = _public_request("GET", "/fapi/v1/exchangeInfo", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance exchange-info response: {result!r}")
        return result

    def time(self, **params: Any) -> dict:
        result = _public_request("GET", "/fapi/v1/time", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance time response: {result!r}")
        return result

    def ticker_price(self, **params: Any) -> Any:
        return _public_request("GET", "/fapi/v1/ticker/price", params)

    def depth(self, **params: Any) -> dict:
        result = _public_request("GET", "/fapi/v1/depth", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance depth response: {result!r}")
        return result

    def get_position_risk(self, **params: Any) -> list:
        result = _signed_request("GET", "/fapi/v2/positionRisk", params)
        return result if isinstance(result, list) else []

    def get_orders(self, **params: Any) -> list:
        result = _signed_request("GET", "/fapi/v1/openOrders", params)
        return result if isinstance(result, list) else []

    def get_all_orders(self, **params: Any) -> list:
        result = _signed_request("GET", "/fapi/v1/allOrders", params)
        return result if isinstance(result, list) else []

    def get_account_trades(self, **params: Any) -> list:
        result = _signed_request("GET", "/fapi/v1/userTrades", params)
        return result if isinstance(result, list) else []

    def income_history(self, **params: Any) -> list:
        result = _signed_request("GET", "/fapi/v1/income", params)
        return result if isinstance(result, list) else []

    def query_order(self, **params: Any) -> dict:
        result = _signed_request("GET", "/fapi/v1/order", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance query-order response: {result!r}")
        return result

    def new_order(self, **params: Any) -> dict:
        result = _signed_request("POST", "/fapi/v1/order", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance new-order response: {result!r}")
        return result

    def cancel_order(self, **params: Any) -> dict:
        result = _signed_request("DELETE", "/fapi/v1/order", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance cancel-order response: {result!r}")
        return result

    def cancel_open_orders(self, **params: Any) -> dict:
        result = _signed_request("DELETE", "/fapi/v1/allOpenOrders", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance cancel-all response: {result!r}")
        return result

    def change_leverage(self, **params: Any) -> dict:
        result = _signed_request("POST", "/fapi/v1/leverage", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance leverage response: {result!r}")
        return result

    def change_margin_type(self, **params: Any) -> dict:
        result = _signed_request("POST", "/fapi/v1/marginType", params)
        if not isinstance(result, dict):
            raise RuntimeError(f"Invalid Binance margin-type response: {result!r}")
        return result

    def leverage_brackets(self, **params: Any) -> Any:
        return _signed_request("GET", "/fapi/v1/leverageBracket", params)


# Public compatibility object expected by legacy modules such as
# order_verification_engine.py. It deliberately avoids the SDK's local-clock
# timestamp generation and uses the synchronised request layer above.
client = BinanceClientCompatibilityFacade()


# Perform an initial best-effort sync. Import remains usable during a temporary
# network outage; the first signed request will retry synchronisation.
try:
    sync_server_time(force=True)
except Exception:
    pass