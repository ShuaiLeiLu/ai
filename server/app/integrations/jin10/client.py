from __future__ import annotations

import json
from dataclasses import dataclass
from itertools import count
from typing import Any

import httpx

from app.core.config import get_settings


@dataclass(frozen=True, slots=True)
class Jin10McpConfig:
    server_url: str
    bearer_token: str
    protocol_version: str = "2025-11-25"
    timeout: float = 20.0

    @classmethod
    def from_settings(cls) -> Jin10McpConfig:
        settings = get_settings()
        return cls(
            server_url=settings.jin10_mcp_server_url,
            bearer_token=settings.jin10_mcp_bearer_token or "",
            protocol_version=settings.jin10_mcp_protocol_version,
            timeout=settings.jin10_mcp_timeout,
        )


class Jin10McpError(RuntimeError):
    """Raised when the Jin10 MCP server returns a protocol or business error."""


class Jin10McpClient:
    def __init__(
        self,
        config: Jin10McpConfig | None = None,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config or Jin10McpConfig.from_settings()
        self._client = http_client
        self._owns_client = http_client is None
        self._session_id: str | None = None
        self._initialized = False
        self._ids = count(1)

    @property
    def is_configured(self) -> bool:
        return bool(self.config.server_url and self.config.bearer_token)

    async def __aenter__(self) -> Jin10McpClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
            self._client = None

    async def initialize(self) -> dict[str, Any]:
        if self._initialized:
            return {}
        if not self.is_configured:
            raise Jin10McpError("Jin10 MCP is not configured")

        result = await self._request(
            "initialize",
            {
                "protocolVersion": self.config.protocol_version,
                "capabilities": {},
                "clientInfo": {"name": "cyber-invest", "version": "0.1.0"},
            },
            include_session=False,
        )
        await self._notify_initialized()
        self._initialized = True
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._initialized_request("tools/list", {})
        return list(result.get("tools") or [])

    async def list_resources(self) -> list[dict[str, Any]]:
        result = await self._initialized_request("resources/list", {})
        return list(result.get("resources") or [])

    async def read_resource(self, uri: str) -> Any:
        result = await self._initialized_request("resources/read", {"uri": uri})
        structured = self._extract_structured_data(result)
        if structured is not None:
            return structured

        for content in result.get("contents") or []:
            text = content.get("text")
            if not text:
                continue
            if content.get("mimeType") == "application/json":
                parsed = json.loads(text)
                return parsed.get("data", parsed)
            return text
        return None

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        result = await self._initialized_request(
            "tools/call",
            {"name": name, "arguments": arguments or {}},
        )
        if result.get("isError"):
            message = self._extract_error_message(result) or "unknown tool error"
            raise Jin10McpError(f"Tool error: {message}")

        structured = self._extract_structured_data(result)
        if structured is not None:
            return structured
        return result.get("content")

    async def _notify_initialized(self) -> None:
        payload = {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}
        response = await self._post(payload, include_session=True)
        if response.status_code not in (200, 202):
            response.raise_for_status()

    async def _initialized_request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        await self.initialize()
        return await self._request(method, params)

    async def _request(
        self,
        method: str,
        params: dict[str, Any],
        *,
        include_session: bool = True,
    ) -> dict[str, Any]:
        payload = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params}
        response = await self._post(payload, include_session=include_session)
        response.raise_for_status()
        if not self._session_id:
            self._session_id = response.headers.get("mcp-session-id")
        data = self._decode_response(response)
        if error := data.get("error"):
            raise Jin10McpError(f"JSON-RPC error: {error.get('message') or error}")
        return data.get("result") or {}

    async def _post(self, payload: dict[str, Any], *, include_session: bool) -> httpx.Response:
        client = self._get_client()
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.config.bearer_token}",
        }
        if include_session and self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return await client.post(self.config.server_url, headers=headers, json=payload)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.config.timeout, connect=10.0),
                trust_env=False,
            )
            self._owns_client = True
        return self._client

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, Any]:
        text = response.text.strip()
        if not text:
            return {}
        if "data:" not in text:
            return response.json()

        data_lines = [
            line.removeprefix("data:").strip()
            for line in text.splitlines()
            if line.startswith("data:")
        ]
        if not data_lines:
            return {}
        return json.loads(data_lines[-1])

    @staticmethod
    def _extract_structured_data(result: dict[str, Any]) -> Any | None:
        structured = result.get("structuredContent")
        if not isinstance(structured, dict):
            return None
        return structured.get("data", structured)

    @staticmethod
    def _extract_error_message(result: dict[str, Any]) -> str | None:
        structured = result.get("structuredContent")
        if isinstance(structured, dict) and structured.get("message"):
            return str(structured["message"])
        for item in result.get("content") or []:
            if isinstance(item, dict) and item.get("text"):
                return str(item["text"])
        return None


_jin10_client: Jin10McpClient | None = None


def get_jin10_mcp_client() -> Jin10McpClient:
    global _jin10_client
    if _jin10_client is None:
        _jin10_client = Jin10McpClient()
    return _jin10_client
