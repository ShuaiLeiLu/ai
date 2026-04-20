from __future__ import annotations

from fastapi import APIRouter

from app.modules.webhooks.schemas import (
    WebhookCreateRequest,
    WebhookEndpoint,
    WebhookToggleRequest,
)
from app.modules.webhooks.service import WebhookService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
service = WebhookService()


@router.get("")
async def list_endpoints() -> ApiResponse[ListResponse[WebhookEndpoint]]:
    items = service.list_endpoints()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.post("")
async def create_endpoint(payload: WebhookCreateRequest) -> ApiResponse[WebhookEndpoint]:
    return ApiResponse(data=service.create_endpoint(payload))


@router.patch("/{webhook_id}/toggle")
async def toggle_endpoint(
    webhook_id: str,
    payload: WebhookToggleRequest,
) -> ApiResponse[WebhookEndpoint]:
    return ApiResponse(data=service.toggle_endpoint(webhook_id, payload))


@router.delete("/{webhook_id}")
async def delete_endpoint(webhook_id: str) -> ApiResponse[WebhookEndpoint]:
    return ApiResponse(data=service.delete_endpoint(webhook_id))
