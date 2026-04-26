from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from app.integrations.jin10.client import Jin10McpClient, Jin10McpConfig, Jin10McpError


def _sse(payload: dict[str, Any]) -> httpx.Response:
    return httpx.Response(200, content=f"event: message\ndata: {json.dumps(payload)}\n\n")


@pytest.mark.asyncio
async def test_client_initializes_once_and_returns_structured_tool_data() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        payload = json.loads(request.content)
        if payload["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "session_1"},
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "protocolVersion": "2025-11-25",
                        "serverInfo": {"name": "jin10"},
                        "capabilities": {},
                    },
                },
            )
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        if payload["method"] == "tools/call":
            assert request.headers["mcp-session-id"] == "session_1"
            assert payload["params"] == {"name": "get_quote", "arguments": {"code": "XAUUSD"}}
            return _sse({
                "jsonrpc": "2.0",
                "id": payload["id"],
                "result": {
                    "structuredContent": {
                        "status": "success",
                        "message": "ok",
                        "data": {"code": "XAUUSD", "name": "现货黄金", "close": "4708.37"},
                    },
                    "content": [{"type": "text", "text": "human text"}],
                },
            })
        raise AssertionError(f"unexpected method {payload['method']}")

    transport = httpx.MockTransport(handler)
    async with Jin10McpClient(
        Jin10McpConfig(server_url="https://mcp.jin10.com/mcp", bearer_token="token"),
        http_client=httpx.AsyncClient(transport=transport),
    ) as client:
        data = await client.call_tool("get_quote", {"code": "XAUUSD"})
        second = await client.call_tool("get_quote", {"code": "XAUUSD"})

    assert data == {"code": "XAUUSD", "name": "现货黄金", "close": "4708.37"}
    assert second["code"] == "XAUUSD"
    assert [json.loads(req.content)["method"] for req in requests].count("initialize") == 1
    assert requests[0].headers["authorization"] == "Bearer token"


@pytest.mark.asyncio
async def test_client_reads_resource_json_text_when_structured_content_is_absent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        if payload["method"] == "initialize":
            return httpx.Response(
                200,
                headers={"mcp-session-id": "session_2"},
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {"protocolVersion": "2025-11-25"},
                },
            )
        if payload["method"] == "notifications/initialized":
            return httpx.Response(202)
        if payload["method"] == "resources/read":
            return httpx.Response(
                200,
                json={
                    "jsonrpc": "2.0",
                    "id": payload["id"],
                    "result": {
                        "contents": [
                            {
                                "uri": "quote://codes",
                                "mimeType": "application/json",
                                "text": json.dumps({
                                    "data": [{"code": "USOIL", "name": "WTI原油"}],
                                }),
                            }
                        ]
                    },
                },
            )
        raise AssertionError(f"unexpected method {payload['method']}")

    async with Jin10McpClient(
        Jin10McpConfig(server_url="https://mcp.jin10.com/mcp", bearer_token="token"),
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    ) as client:
        data = await client.read_resource("quote://codes")

    assert data == [{"code": "USOIL", "name": "WTI原油"}]


@pytest.mark.asyncio
async def test_client_raises_for_json_rpc_and_tool_business_errors() -> None:
    responses = iter([
        httpx.Response(
            200,
            headers={"mcp-session-id": "session_3"},
            json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25"}},
        ),
        httpx.Response(202),
        httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "error": {"code": -32602, "message": "bad"},
            },
        ),
    ])

    async with Jin10McpClient(
        Jin10McpConfig(server_url="https://mcp.jin10.com/mcp", bearer_token="token"),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: next(responses)),
        ),
    ) as client:
        with pytest.raises(Jin10McpError, match="JSON-RPC error"):
            await client.call_tool("get_quote", {"code": "BAD"})

    responses = iter([
        httpx.Response(
            200,
            headers={"mcp-session-id": "session_4"},
            json={"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-11-25"}},
        ),
        httpx.Response(202),
        httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "result": {
                    "isError": True,
                    "structuredContent": {
                        "status": "error",
                        "message": "unknown code",
                        "data": None,
                    },
                },
            },
        ),
    ])

    async with Jin10McpClient(
        Jin10McpConfig(server_url="https://mcp.jin10.com/mcp", bearer_token="token"),
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _request: next(responses)),
        ),
    ) as client:
        with pytest.raises(Jin10McpError, match="Tool error"):
            await client.call_tool("get_quote", {"code": "BAD"})
