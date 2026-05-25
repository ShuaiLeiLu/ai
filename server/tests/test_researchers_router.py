from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.page_cache import save_cached
from app.modules.researchers.schemas import ResearcherMarketCard


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
async def test_researcher_market_reads_cached_snapshot_before_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.researchers import router as researchers_router

    redis = FakeRedis()
    cached = [
        ResearcherMarketCard(
            id="r_cached",
            name="缓存研究员",
            introduction="来自 Redis",
            level="LV.1",
            hire_count=3,
            version="v1",
            tags=["cached"],
        )
    ]
    await save_cached(redis, "researchers:market:q=:page=1:size=20", {"items": cached, "total": 1}, ttl_seconds=120)

    async def fail_market(*_args: object, **_kwargs: object) -> tuple[list[ResearcherMarketCard], int]:
        raise AssertionError("cached researcher market must not call service")

    monkeypatch.setattr(researchers_router.service, "async_list_market", fail_market)
    monkeypatch.setattr(
        "app.modules.researchers.router.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
        raising=False,
    )

    response = await researchers_router.list_market(
        q=None,
        page=1,
        page_size=20,
        session=object(),  # type: ignore[arg-type]
    )

    assert response.data.items == cached
    assert response.data.total == 1
