"""API v1 route aggregation."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, status

from app.api.v1.market import router as market_router

from app.api.v1.ai import router as ai_router

from app.api.v1.testnet import router as testnet_router

from app.api.v1.auto_testnet import router as auto_testnet_router

from app.api.v1.journal import router as journal_router

from app.api.v1.dashboard import router as dashboard_router

from app.api.v1.portfolio import router as portfolio_router

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(status.router, prefix="/status", tags=["status"])
api_router.include_router(market_router)
api_router.include_router(ai_router)
api_router.include_router(testnet_router)
api_router.include_router(auto_testnet_router)
api_router.include_router(journal_router)
api_router.include_router(dashboard_router)
api_router.include_router(portfolio_router)