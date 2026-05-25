from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.modules.page_cache import save_cached
from app.modules.tasks.schemas import TaskSummary


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
async def test_task_list_reads_cached_snapshot_before_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.tasks import router as tasks_router

    redis = FakeRedis()
    now = datetime(2026, 5, 25, 9, 30, tzinfo=UTC)
    cached = [
        TaskSummary(
            task_id="task_cached",
            title="缓存任务",
            researcher_id="r_cached",
            schedule_type="one_time",
            schedule_config={},
            status="ACTIVE",
            lifecycle_status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
    ]
    await save_cached(redis, "tasks:list:u_test:status=all:schedule=all", cached, ttl_seconds=120)

    async def fail_tasks(*_args: object, **_kwargs: object) -> list[TaskSummary]:
        raise AssertionError("cached task list must not call service")

    monkeypatch.setattr(tasks_router.service, "list_tasks", fail_tasks)
    monkeypatch.setattr(
        "app.modules.tasks.router.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
        raising=False,
    )

    response = await tasks_router.list_tasks(
        status=None,
        schedule_type=None,
        user_id="u_test",
        session=object(),  # type: ignore[arg-type]
    )

    assert response.data.items == cached
