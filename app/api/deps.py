"""Shared FastAPI dependencies."""

from app.core.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Inject application settings into route handlers."""
    return get_settings()
