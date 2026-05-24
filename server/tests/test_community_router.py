from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_optional_session
from app.core.security import get_current_user_id
from app.modules.community.router import legacy_router


@pytest.mark.asyncio
async def test_community_list_falls_back_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(legacy_router, prefix="/api/v1")

    async def no_session():
        yield None

    app.dependency_overrides[get_optional_session] = no_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ai-community/post/list?q=半导体&scope=all&sort=hot")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] >= 1
    assert "半导体" in payload["items"][0]["title"] or "半导体" in payload["items"][0]["excerpt"]


@pytest.mark.asyncio
async def test_community_detail_and_comments_fall_back_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(legacy_router, prefix="/api/v1")

    async def no_session():
        yield None

    app.dependency_overrides[get_optional_session] = no_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        detail_response = await client.get("/api/v1/ai-community/post/community_sample_1")
        comments_response = await client.get("/api/v1/ai-community/comment/list?post_id=community_sample_1")

    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["post_id"] == "community_sample_1"
    assert detail["comment_list"]

    assert comments_response.status_code == 200
    comments = comments_response.json()["data"]
    assert comments["total"] >= 1
    assert comments["items"][0]["author_type"] == "ai_researcher"
    assert comments["items"][1]["reply_to_id"] == "community_comment_1"
    assert comments["items"][1]["reply_to_author"] == "基本面分析·阿平"


@pytest.mark.asyncio
async def test_community_comment_create_falls_back_with_reply_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(legacy_router, prefix="/api/v1")

    async def no_session():
        yield None

    app.dependency_overrides[get_optional_session] = no_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/ai-community/comment/create",
            json={
                "post_id": "community_sample_1",
                "content": "@基本面分析·阿平 我补一个订单角度",
                "reply_to_id": "community_comment_1",
            },
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["content"] == "@基本面分析·阿平 我补一个订单角度"
    assert payload["reply_to_id"] == "community_comment_1"
    assert payload["reply_to_author"] == "基本面分析·阿平"


@pytest.mark.asyncio
async def test_community_mention_config_falls_back_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(legacy_router, prefix="/api/v1")

    async def no_session():
        yield None

    async def fake_user_id():
        return "u_test"

    app.dependency_overrides[get_optional_session] = no_session
    app.dependency_overrides[get_current_user_id] = fake_user_id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/ai-community/mention/config")

    assert response.status_code == 200
    researchers = response.json()["data"]["researchers"]
    assert len(researchers) >= 3
    assert researchers[0]["name"] == "基本面分析·阿平"
