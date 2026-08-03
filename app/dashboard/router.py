"""FastAPI router for the TitanAI operations dashboard."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.dashboard.service import (
    get_open_positions,
    get_overview,
    get_performance_summary,
    get_recent_cycles,
    get_scheduler_health,
)

router = APIRouter(tags=["Dashboard"])
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page() -> HTMLResponse:
    if not TEMPLATE_PATH.exists():
        return HTMLResponse(
            "<h1>TitanAI dashboard template is missing.</h1>",
            status_code=500,
        )
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))


@router.get("/api/dashboard/overview")
async def dashboard_overview() -> dict:
    return get_overview()


@router.get("/api/dashboard/health")
async def dashboard_health() -> dict:
    return get_scheduler_health()


@router.get("/api/dashboard/performance")
async def dashboard_performance() -> dict:
    return get_performance_summary()


@router.get("/api/dashboard/positions")
async def dashboard_positions(
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    return {"items": get_open_positions(limit=limit)}


@router.get("/api/dashboard/cycles")
async def dashboard_cycles(
    limit: int = Query(default=50, ge=1, le=500),
) -> dict:
    return {"items": get_recent_cycles(limit=limit)}