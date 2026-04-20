from __future__ import annotations

from datetime import datetime

from pydantic import AnyHttpUrl, Field

from app.schemas.common import SchemaModel


class WebhookEndpoint(SchemaModel):
    webhook_id: str
    name: str
    url: AnyHttpUrl
    secret_masked: str
    enabled: bool
    created_at: datetime


class WebhookCreateRequest(SchemaModel):
    name: str = Field(min_length=1, max_length=80)
    url: AnyHttpUrl
    secret: str = Field(min_length=6, max_length=128)


class WebhookToggleRequest(SchemaModel):
    enabled: bool
