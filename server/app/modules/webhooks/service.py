from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, status

from app.modules.webhooks.schemas import WebhookCreateRequest, WebhookEndpoint, WebhookToggleRequest


class WebhookService:
    """Webhook 配置服务。

    当前支持最小化增查，后续将扩展签名校验与投递重试策略。
    """

    def __init__(self) -> None:
        self._endpoints: dict[str, WebhookEndpoint] = {}

    def list_endpoints(self) -> list[WebhookEndpoint]:
        return sorted(
            self._endpoints.values(),
            key=lambda endpoint: (endpoint.created_at, endpoint.webhook_id),
            reverse=True,
        )

    def create_endpoint(self, payload: WebhookCreateRequest) -> WebhookEndpoint:
        webhook_id = f"wh_{uuid4().hex[:10]}"
        # 不落原始密钥，返回脱敏字段给前端展示。
        endpoint = WebhookEndpoint(
            webhook_id=webhook_id,
            name=payload.name,
            url=payload.url,
            secret_masked=f"{payload.secret[:2]}***{payload.secret[-2:]}",
            enabled=True,
            created_at=datetime.now(tz=UTC),
        )
        self._endpoints[webhook_id] = endpoint
        return endpoint

    def toggle_endpoint(self, webhook_id: str, payload: WebhookToggleRequest) -> WebhookEndpoint:
        endpoint = self._get_endpoint_or_404(webhook_id)
        endpoint.enabled = payload.enabled
        return endpoint

    def delete_endpoint(self, webhook_id: str) -> WebhookEndpoint:
        endpoint = self._get_endpoint_or_404(webhook_id)
        del self._endpoints[webhook_id]
        return endpoint

    def _get_endpoint_or_404(self, webhook_id: str) -> WebhookEndpoint:
        endpoint = self._endpoints.get(webhook_id)
        if endpoint is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook 不存在")
        return endpoint
