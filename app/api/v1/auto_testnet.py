from fastapi import APIRouter, Query, HTTPException
import logging

from app.trader.auto_testnet_runner import run_auto_testnet_cycle

router = APIRouter()
logger = logging.getLogger(__name__)


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

        return result

    except Exception as e:

        logger.exception(e)

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )