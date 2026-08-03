"""FastAPI endpoints for TitanAI v20 analytics."""
from __future__ import annotations
from fastapi import APIRouter
from app.analytics.service import get_analytics_snapshot

router = APIRouter(prefix="/api/dashboard/analytics", tags=["Dashboard Analytics"])

@router.get("")
async def analytics_snapshot() -> dict:
    return get_analytics_snapshot()

@router.get("/summary")
async def analytics_summary() -> dict:
    return get_analytics_snapshot()["summary"]

@router.get("/equity-curve")
async def equity_curve() -> dict:
    return {"items": get_analytics_snapshot()["equity_curve"]}

@router.get("/pnl")
async def pnl_series() -> dict:
    snapshot = get_analytics_snapshot()
    return {"daily": snapshot["daily_pnl"], "weekly": snapshot["weekly_pnl"], "monthly": snapshot["monthly_pnl"]}

@router.get("/symbols")
async def symbol_performance() -> dict:
    return {"items": get_analytics_snapshot()["symbol_performance"]}
