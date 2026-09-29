from fastapi import APIRouter, Query, HTTPException
import logging

from app.trader.auto_testnet_runner import run_auto_testnet_cycle
from app.service.service_state_store import get_state, set_state

router = APIRouter()
logger = logging.getLogger(__name__)

# Persistent key shared by the scanner/worker and read-only dashboard API.
LATEST_SCANNER_STATE_KEY = "latest_scanner_result"


@router.get("/auto-testnet/run")
async def auto_testnet_run(
    execute_trade: bool = Query(False),
    symbol: str = Query("BTCUSDT"),
    quantity: float = Query(0.001),
):
    """
    Run one complete TitanAI cycle.

    execute_trade=False
        -> Analysis only

    execute_trade=True
        -> Execute Testnet order only if validation passes.
    """

    try:

        result = await run_auto_testnet_cycle(
            quantity=quantity,
            execute_trade=execute_trade,
        )

        # Do not overwrite a good dashboard snapshot with the
        # "another cycle is already running" response.
        if (
            isinstance(result, dict)
            and result.get("scan")
            and result.get("reason") != "Another auto-testnet cycle is already running"
        ):
            set_state(
                LATEST_SCANNER_STATE_KEY,
                result,
            )

        return result

    except Exception as e:

        logger.exception(e)

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


@router.get("/auto-testnet/status")
async def auto_testnet_status():
    """Return the latest completed scanner cycle without starting a new cycle."""
    latest_result = get_state(
        LATEST_SCANNER_STATE_KEY,
        None,
    )

    if latest_result is None:
        return {
            "status": "waiting",
            "reason": "No completed scanner cycle is persisted yet",
            "scan": None,
        }

    return latest_result
