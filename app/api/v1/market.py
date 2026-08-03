from fastapi import APIRouter, HTTPException
from app.services.market_data import get_prices
from app.services.candles import get_klines, normalize_klines
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/market/prices")
async def market_prices():
    try:
        data = await get_prices()

        if not data:
            raise HTTPException(
                status_code=500,
                detail="Failed to fetch market data",
            )

        return {
            "status": "success",
            "data": data,
        }

    except Exception as e:
        logger.error(f"Market API error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error",
        )


@router.get("/market/klines")
async def market_klines(
    symbol: str = "BTCUSDT",
    interval: str = "15m",
    limit: int = 100,
):
    try:
        raw_data = await get_klines(symbol, interval, limit)
        normalized_data = normalize_klines(raw_data)

        return {
            "status": "success",
            "symbol": symbol,
            "interval": interval,
            "data": normalized_data,
        }

    except Exception as e:
        logger.error(f"Klines API error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Failed to fetch kline data",
        )