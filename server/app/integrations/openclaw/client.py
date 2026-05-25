from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class OpenClawTradePushConfig:
    endpoint_url: str
    secret: str = ""
    timeout: float = 5.0

    @classmethod
    def from_settings(cls) -> OpenClawTradePushConfig:
        settings = get_settings()
        return cls(
            endpoint_url=settings.openclaw_push_url or "",
            secret=settings.openclaw_push_secret or "",
            timeout=settings.openclaw_push_timeout,
        )


class OpenClawTradePushClient:
    def __init__(
        self,
        config: OpenClawTradePushConfig | None = None,
        *,
        endpoint_url: str | None = None,
        secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if config is not None:
            self.config = config
        elif endpoint_url is not None:
            self.config = OpenClawTradePushConfig(
                endpoint_url=endpoint_url,
                secret=secret or "",
            )
        else:
            self.config = OpenClawTradePushConfig.from_settings()
            if secret is not None:
                self.config = OpenClawTradePushConfig(
                    endpoint_url=self.config.endpoint_url,
                    secret=secret,
                    timeout=self.config.timeout,
                )
        self._client = http_client
        self._owns_client = http_client is None

    @property
    def is_configured(self) -> bool:
        return bool(self.config.endpoint_url)

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def push_trade(self, payload: dict[str, Any]) -> None:
        if not self.is_configured:
            return

        body = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-OpenClaw-Event": str(payload.get("event_type", "")),
            "X-OpenClaw-Event-Id": str(payload.get("event_id", "")),
        }
        if self.config.secret:
            signature = hmac.new(
                self.config.secret.encode("utf-8"),
                body,
                hashlib.sha256,
            ).hexdigest()
            headers["X-OpenClaw-Signature"] = f"sha256={signature}"

        response = await self._get_client().post(
            self.config.endpoint_url,
            content=body,
            headers=headers,
        )
        response.raise_for_status()

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout, connect=3.0),
                trust_env=False,
            )
            self._owns_client = True
        return self._client
