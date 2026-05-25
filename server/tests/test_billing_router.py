from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_optional_session
from app.core.security import get_current_user_id
from app.modules.billing.schemas import BatteryPackage, MembershipInfo
from app.modules.billing.router import router
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
async def test_billing_power_packages_fallback_when_database_unavailable() -> None:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    async def no_session():
        yield None

    async def fake_user_id():
        return "u_test"

    app.dependency_overrides[get_optional_session] = no_session
    app.dependency_overrides[get_current_user_id] = fake_user_id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/billing/battery/packages")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["total"] == 4
    assert payload["items"][1]["name"] == "5,000 算力"
    assert payload["items"][1]["battery_count"] == 5000


@pytest.mark.asyncio
async def test_billing_membership_reads_cached_snapshot_before_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from app.modules.billing import router as billing_router

    redis = FakeRedis()
    cached = MembershipInfo(
        level="VIP2",
        display_name="缓存会员",
        battery_discount=0.9,
        unlocked_features=["cached"],
    )
    await save_cached(redis, "billing:membership:u_test", cached, ttl_seconds=120)

    async def fail_membership(*_args: object, **_kwargs: object) -> MembershipInfo:
        raise AssertionError("cached membership must not call service")

    monkeypatch.setattr(billing_router.service, "async_get_membership", fail_membership)
    monkeypatch.setattr(
        "app.modules.billing.router.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
        raising=False,
    )

    response = await billing_router.get_membership(user_id="u_test", session=object())  # type: ignore[arg-type]

    assert response.data == cached


@pytest.mark.asyncio
async def test_billing_packages_reads_cached_snapshot_before_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from app.modules.billing import router as billing_router

    redis = FakeRedis()
    cached = [BatteryPackage(package_id="pkg_cached", name="缓存套餐", battery_count=100, price=1.0)]
    await save_cached(redis, "billing:battery-packages", cached, ttl_seconds=120)

    async def fail_packages(*_args: object, **_kwargs: object) -> list[BatteryPackage]:
        raise AssertionError("cached packages must not call service")

    monkeypatch.setattr(billing_router.service, "async_list_packages", fail_packages)
    monkeypatch.setattr(
        "app.modules.billing.router.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
        raising=False,
    )

    response = await billing_router.list_battery_packages(session=object())  # type: ignore[arg-type]

    assert response.data.items == cached
