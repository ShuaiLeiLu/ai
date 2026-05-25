from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_optional_session
from app.modules.documents.schemas import DocumentSummary
from app.modules.documents.router import router
from app.modules.page_cache import save_cached


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        self.store[key] = value
        return True

    async def delete(self, key: str) -> int:
        existed = key in self.store
        self.store.pop(key, None)
        return int(existed)


class FakeRedisFactory:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis

    def get_client(self) -> FakeRedis:
        return self._redis


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


@pytest.mark.asyncio
async def test_document_list_reads_cached_snapshot_before_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from datetime import UTC, datetime
    from types import SimpleNamespace

    from app.modules.documents import router as documents_router

    redis = FakeRedis()
    cached_items = [
        DocumentSummary(
            document_id="doc_cached",
            title="缓存研报",
            researcher_name="缓存研究员",
            document_type="market",
            view_count=1,
            like_count=2,
            created_at=datetime(2026, 5, 25, 9, 30, tzinfo=UTC),
        )
    ]
    await save_cached(redis, "documents:list:all:none:none:none", cached_items, ttl_seconds=120)

    async def fail_list(*_args: object, **_kwargs: object) -> tuple[list[DocumentSummary], int]:
        raise AssertionError("cached document list must not call service")

    monkeypatch.setattr(documents_router.service, "async_list_documents", fail_list)
    monkeypatch.setattr(
        "app.modules.documents.router.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
        raising=False,
    )

    response = await documents_router.list_documents(
        doc_type=None,
        limit=None,
        page=None,
        page_size=None,
        session=object(),  # type: ignore[arg-type]
    )

    assert response.data.items == cached_items
