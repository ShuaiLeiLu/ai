from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.ecosystem.schemas import SkillItem
from app.modules.page_cache import save_cached


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        self.store[key] = value
        return True


class FakeRedisFactory:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis

    def get_client(self) -> FakeRedis:
        return self._redis


@pytest.mark.asyncio
async def test_ecosystem_skills_reads_cached_snapshot_before_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.ecosystem import router as ecosystem_router

    redis = FakeRedis()
    cached = [SkillItem(skill_id="skill_cached", name="缓存技能", description="来自 Redis", installed=False)]
    await save_cached(redis, "ecosystem:skills:installed=all", cached, ttl_seconds=120)

    async def fail_skills(*_args: object, **_kwargs: object) -> list[SkillItem]:
        raise AssertionError("cached ecosystem skills must not call service")

    monkeypatch.setattr(ecosystem_router.service, "async_list_skills", fail_skills)
    monkeypatch.setattr(
        "app.modules.ecosystem.router.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
        raising=False,
    )

    response = await ecosystem_router.list_skills(installed=None, session=object())  # type: ignore[arg-type]

    assert response.data.items == cached
