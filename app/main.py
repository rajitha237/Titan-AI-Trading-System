"""FastAPI application entry point."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.deps import get_app_settings
from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.logging import setup_logging

from app.schemas.common import HealthResponse, RootResponse

# Dashboard
from app.dashboard.router import router as dashboard_router

# Analytics Dashboard
from app.dashboard.analytics_router import router as analytics_router


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    setup_logging(settings)

    logger.info("Starting %s [%s]", settings.app_name, settings.app_env)

    yield

    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="AI-powered cryptocurrency trading platform (TitanAI)",
        version="0.2.0",
        debug=settings.app_debug,
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.mount(
        "/static",
        StaticFiles(directory="app/static"),
        name="static",
    )

    # ==========================
    # API
    # ==========================
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # ==========================
    # Dashboard
    # ==========================
    app.include_router(dashboard_router)

    # ==========================
    # Analytics
    # ==========================
    app.include_router(analytics_router)

    @app.get("/", response_model=RootResponse, tags=["root"])
    async def root(
        settings: Settings = Depends(get_app_settings),
    ) -> RootResponse:
        return RootResponse(
            service=settings.app_name,
            version="0.2.0",
            environment=settings.app_env,
            docs="/docs",
        )

    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check(
        settings: Settings = Depends(get_app_settings),
    ) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
        )

    return app


app = create_app()