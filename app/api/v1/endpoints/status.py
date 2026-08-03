"""Platform status endpoints."""

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.schemas.common import StatusResponse

router = APIRouter()


@router.get("", response_model=StatusResponse)
async def get_status(settings: Settings = Depends(get_app_settings)) -> StatusResponse:
    return StatusResponse(
        service=settings.app_name,
        environment=settings.app_env,
        version="0.1.0",
    )
