from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from app.modules.preopen import snapshots
from app.modules.preopen.schemas import HotNewsItem
from app.modules.preopen.snapshot_cache import load_snapshot, save_snapshot
from app.modules.preopen.snapshot_refresher import RefreshTarget, _refresh_target


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.store.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool = False) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    async def rename(self, source: str, target: str) -> None:
        self.store[target] = self.store.pop(source)

    async def expire(self, key: str, seconds: int) -> bool:
        return key in self.store

    async def eval(self, script: str, numkeys: int, key: str, token: str) -> int:
        if self.store.get(key) == token:
            del self.store[key]
            return 1
        return 0


def _hot_news_item(title: str) -> HotNewsItem:
    return HotNewsItem(
        news_id=f"hn_{title}",
        title=title,
        summary=title,
        source="测试",
        published_at=datetime(2026, 4, 26, 9, 30, tzinfo=UTC),
        heat=100,
        sentiment="neutral",
        symbols=[],
        jump_type="news",
        jump_target="/news",
    )


@pytest.mark.asyncio
async def test_preopen_snapshot_round_trip() -> None:
    redis = FakeRedis()
    item = _hot_news_item("快讯")

    await save_snapshot(redis, snapshots.HOT_NEWS, [item])

    raw = redis.store[snapshots.HOT_NEWS.redis_key]
    payload = json.loads(raw)
    loaded = await load_snapshot(redis, snapshots.HOT_NEWS)

    assert payload["name"] == "hot-news"
    assert payload["updated_at"]
    assert loaded == [item]


@pytest.mark.asyncio
async def test_refresh_target_keeps_last_snapshot_when_required_list_is_empty() -> None:
    redis = FakeRedis()
    old_item = _hot_news_item("旧快讯")
    await save_snapshot(redis, snapshots.HOT_NEWS, [old_item])

    async def empty_fetch(_service: object) -> list[HotNewsItem]:
        return []

    refreshed = await _refresh_target(
        redis,
        object(),  # type: ignore[arg-type]
        RefreshTarget(spec=snapshots.HOT_NEWS, fetch=empty_fetch, min_items=1),
    )
    loaded = await load_snapshot(redis, snapshots.HOT_NEWS)

    assert refreshed is False
    assert loaded == [old_item]
