from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class OpenClawTradePushConfig:
    endpoint_url: str
    token: str = ""
    timeout: float = 5.0

    @classmethod
    def from_settings(cls) -> OpenClawTradePushConfig:
        settings = get_settings()
        return cls(
            endpoint_url=settings.openclaw_push_url or "",
            token=settings.openclaw_push_token or settings.openclaw_push_secret or "",
            timeout=settings.openclaw_push_timeout,
        )


class OpenClawTradePushClient:
    def __init__(
        self,
        config: OpenClawTradePushConfig | None = None,
        *,
        endpoint_url: str | None = None,
        token: str | None = None,
        secret: str | None = None,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        if config is not None:
            self.config = config
        elif endpoint_url is not None:
            self.config = OpenClawTradePushConfig(
                endpoint_url=endpoint_url,
                token=token or secret or "",
            )
        else:
            self.config = OpenClawTradePushConfig.from_settings()
            auth_token = token if token is not None else secret
            if auth_token is not None:
                self.config = OpenClawTradePushConfig(
                    endpoint_url=self.config.endpoint_url,
                    token=auth_token,
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

    async def push_trade(self, payload: dict[str, object]) -> None:
        if not self.is_configured:
            return

        message = str(payload.get("message") or "").strip()
        if not message:
            return
        body = json.dumps(
            {"message": message},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"

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
