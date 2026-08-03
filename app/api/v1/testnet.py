from fastapi import APIRouter, HTTPException
import logging

from app.exchange.binance_testnet_client import (
    get_account_balance,
    get_open_positions,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/testnet/status")
async def testnet_status():
    try:
        balance = get_account_balance()
        positions = get_open_positions()

        return {
            "status": "success",
            "balance": balance,
            "open_positions": positions,
        }

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))