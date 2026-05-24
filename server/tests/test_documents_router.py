from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_optional_session
from app.modules.documents.router import router


@pytest.mark.asyncio
async def test_document_detail_falls_back_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def no_session():
        yield None

    app.dependency_overrides[get_optional_session] = no_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/documents/d_market_1")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["document_id"] == "d_market_1"
    assert payload["content_markdown"]
    assert payload["workflow_nodes"]


@pytest.mark.asyncio
async def test_document_list_falls_back_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def no_session():
        yield None

    app.dependency_overrides[get_optional_session] = no_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/documents")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 2
    assert payload["items"][0]["document_id"]


@pytest.mark.asyncio
async def test_document_comments_fall_back_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def no_session():
        yield None

    app.dependency_overrides[get_optional_session] = no_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/documents/d_market_1/comments")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 1
    assert payload["items"][0]["author_type"] == "ai_researcher"
    assert payload["items"][1]["reply_to_id"] == "dc_1"
    assert payload["items"][1]["reply_to_author"] == "基本面分析·阿平"


@pytest.mark.asyncio
async def test_document_comment_create_falls_back_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def no_session():
        yield None

    app.dependency_overrides[get_optional_session] = no_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/documents/d_market_1/comments",
            json={"content": "@基本面分析·阿平 请补充风险点", "reply_to_id": "dc_1"},
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["content"] == "@基本面分析·阿平 请补充风险点"
    assert payload["author_type"] == "user"
    assert payload["reply_to_id"] == "dc_1"
    assert payload["reply_to_author"] == "基本面分析·阿平"
