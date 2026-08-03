from fastapi import APIRouter, HTTPException
import logging

from app.services.market_data import get_prices
from app.services.orderbook import get_order_book, analyze_order_book
from app.services.open_interest import get_open_interest
from app.services.funding_rate import get_funding_rate
from app.services.candles import get_klines

from app.ai.signal_engine import generate_signals
from app.ai.scoring_engine import calculate_ai_score
from app.ai.strategy_engine import make_trade_decision
from app.ai.technical_engine import analyze_technical
from app.ai.multi_timeframe_engine import analyze_multi_timeframe

from app.risk.risk_engine import calculate_risk_plan

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/ai/signals")
async def ai_signals():
    try:
        prices = await get_prices()
        signals = generate_signals(prices)

        order_book = await get_order_book("BTCUSDT", 100)
        order_book_analysis = analyze_order_book(order_book)

        open_interest = await get_open_interest("BTCUSDT")
        funding_rate = await get_funding_rate("BTCUSDT")

        candles = await get_klines("BTCUSDT", "15m", 150)
        technical = analyze_technical(candles)

        multi_timeframe = await analyze_multi_timeframe("BTCUSDT")

        ai_score = calculate_ai_score(
            order_book_analysis,
            open_interest,
            funding_rate,
            technical,
            multi_timeframe,
        )

        final_decision = make_trade_decision(ai_score)

        risk_plan = calculate_risk_plan(
            balance=30.0,
            risk_percent=1.0,
            leverage=5.0,
        )

        return {
            "status": "success",
            "signals": signals,
            "order_book": order_book_analysis,
            "open_interest": open_interest,
            "funding_rate": funding_rate,
            "technical": technical,
            "multi_timeframe": multi_timeframe,
            "ai_score": ai_score,
            "final_decision": final_decision,
            "risk_plan": risk_plan,
        }

    except Exception as e:
        logger.exception(e)
        raise HTTPException(status_code=500, detail=str(e))