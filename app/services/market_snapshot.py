"""
TitanAI Market Snapshot

Collects all live market information for one symbol.

Includes:
- Order Book
- Order Flow
- Liquidity
- Liquidity Trend
- Liquidity Sweep
- Absorption
- Iceberg Detection
- Whale Activity
- Market Structure
- Volume Profile
- VWAP
- Fair Value Gaps
- Open Interest
- Funding Rate
- Candles
"""

from app.services.orderbook import (
    get_order_book,
    analyze_order_book,
)
from app.services.order_flow import get_order_flow_analysis
from app.services.open_interest import get_open_interest
from app.services.funding_rate import get_funding_rate
from app.services.candles import get_klines

from app.services.liquidity_engine import analyze_liquidity
from app.services.liquidity_tracker import record_liquidity
from app.services.liquidity_sweep import detect_liquidity_sweep
from app.services.absorption_detector import detect_absorption
from app.services.iceberg_detector import detect_iceberg
from app.services.whale_engine import analyze_whale_activity
from app.services.volume_profile import analyze_volume_profile
from app.services.vwap_engine import analyze_vwap

from app.ai.market_structure_engine import analyze_market_structure
from app.ai.fvg_engine import analyze_fair_value_gaps


async def get_market_snapshot(symbol: str) -> dict:
    order_book = await get_order_book(
        symbol,
        100,
    )

    order_book_analysis = analyze_order_book(
        order_book
    )

    liquidity = analyze_liquidity(
        order_book
    )

    liquidity_trend = record_liquidity(
        symbol=symbol,
        liquidity=liquidity,
    )

    order_flow = await get_order_flow_analysis(
        symbol
    )

    whale_activity = await analyze_whale_activity(
        symbol
    )

    open_interest = await get_open_interest(
        symbol
    )

    funding_rate = await get_funding_rate(
        symbol
    )

    candles = await get_klines(
        symbol,
        "15m",
        150,
    )

    if not candles:
        raise ValueError(
            f"No candle data returned for {symbol}"
        )

    latest_candle = candles[-1]

    if isinstance(latest_candle, dict):
        latest_price = float(
            latest_candle["close"]
        )
    else:
        latest_price = float(
            latest_candle[4]
        )

    market_structure = analyze_market_structure(
        candles
    )

    volume_profile = analyze_volume_profile(
        candles=candles,
        bins=40,
    )

    vwap = analyze_vwap(
        candles=candles,
        mean_reversion_threshold_percent=1.5,
    )

    fair_value_gaps = analyze_fair_value_gaps(
        candles=candles,
        minimum_gap_percent=0.02,
        max_returned_gaps=10,
    )

    liquidity_sweep = detect_liquidity_sweep(
        price=latest_price,
        liquidity=liquidity,
        liquidity_trend=liquidity_trend,
        order_flow=order_flow,
    )

    absorption = detect_absorption(
        price=latest_price,
        order_book=order_book_analysis,
        order_flow=order_flow,
        liquidity=liquidity,
        liquidity_trend=liquidity_trend,
    )

    iceberg = detect_iceberg(
        order_book
    )

    return {
        "symbol": symbol,
        "price": latest_price,
        "candles": candles,

        "order_book": order_book_analysis,
        "order_flow": order_flow,

        "liquidity": liquidity,
        "liquidity_trend": liquidity_trend,
        "liquidity_sweep": liquidity_sweep,

        "absorption": absorption,
        "iceberg": iceberg,

        "whale_activity": whale_activity,
        "market_structure": market_structure,

        "volume_profile": volume_profile,
        "vwap": vwap,
        "fair_value_gaps": fair_value_gaps,

        "open_interest": open_interest,
        "funding_rate": funding_rate,
    }