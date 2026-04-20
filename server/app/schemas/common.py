from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class SchemaModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(SchemaModel):
    status: str
    service: str
    version: str
    environment: str
    timestamp: datetime


class ApiResponse(SchemaModel, Generic[T]):
    success: bool = True
    data: T


class ListResponse(SchemaModel, Generic[T]):
    items: list[T]
    total: int


class OperationResponse(SchemaModel):
    message: str
    resource_id: str | None = None
