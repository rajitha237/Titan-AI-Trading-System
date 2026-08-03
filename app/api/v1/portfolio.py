from fastapi import APIRouter, HTTPException
import logging

from app.trader.portfolio_scanner import scan_portfolio

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/portfolio/scan")
async def portfolio_scan():
    """
    Scan the dynamic trading universe and return ranked setups.
    """
    try:
        result = await scan_portfolio()

        return result

    except Exception as e:
        logger.exception(e)

        raise HTTPException(
            status_code=500,
            detail="Portfolio scan failed",
        )