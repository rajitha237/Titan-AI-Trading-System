from fastapi import APIRouter, HTTPException
import logging

from app.trader.trade_journal import get_journal_entries

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/journal")
async def journal_entries():
    try:
        entries = get_journal_entries()

        return {
            "status": "success",
            "total_entries": len(entries),
            "entries": entries,
        }

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))