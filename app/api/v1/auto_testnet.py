from fastapi import APIRouter, Query, HTTPException
import logging

from app.trader.auto_testnet_runner import run_auto_testnet_cycle

router = APIRouter()
logger = logging.getLogger(__name__)

# Latest successfully completed cycle for read-only dashboard polling.
# Temporary process-local cache; persistent/shared storage comes with worker cutover.
_latest_cycle_result = None


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
            global _latest_cycle_result
            _latest_cycle_result = result

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
    if _latest_cycle_result is None:
        return {
            "status": "waiting",
            "reason": "No completed scanner cycle is cached yet",
            "scan": None,
        }

    return _latest_cycle_result
