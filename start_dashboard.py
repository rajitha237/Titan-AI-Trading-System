"""Run the TitanAI FastAPI dashboard.

This launcher first tries the existing `app.main:app`. If your current main.py
has the dashboard router included, use:

    uvicorn app.main:app --reload

This standalone launcher exists as a safe fallback.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from app.dashboard.router import router as dashboard_router

app = FastAPI(
    title="TitanAI Dashboard",
    version="0.19.0",
)
app.include_router(dashboard_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "TitanAI Dashboard"}


if __name__ == "__main__":
    uvicorn.run(
        "start_dashboard:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )