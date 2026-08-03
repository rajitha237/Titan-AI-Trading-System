"""Shared API schemas."""

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class RootResponse(BaseSchema):
    service: str
    version: str
    environment: str
    docs: str


class HealthResponse(BaseSchema):
    status: str
    service: str


class StatusResponse(BaseSchema):
    service: str
    environment: str
    version: str
