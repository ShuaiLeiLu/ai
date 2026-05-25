from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.page_cache import save_cached
from app.modules.trading.schemas import TradingAccount, TradingAllData


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
async def test_trading_all_reads_cached_snapshot_before_service(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.trading import router as trading_router

    redis = FakeRedis()
    cached = TradingAllData(
        account=TradingAccount(
            account_id="acct_cached",
            initial_capital=1_000_000,
            total_asset=1_001_000,
            available_cash=501_000,
            holding_value=500_000,
            daily_pnl=1_000,
        ),
        positions=[],
        records=[],
        logs=[],
    )
    await save_cached(redis, "trading:all:u_test:r_test", cached, ttl_seconds=60)

    async def fail_all(*_args: object, **_kwargs: object) -> TradingAllData:
        raise AssertionError("cached trading all must not call service")

    monkeypatch.setattr(trading_router.service, "async_get_all", fail_all)
    monkeypatch.setattr(
        "app.modules.trading.router.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
        raising=False,
    )

    response = await trading_router.trading_all(
        researcher_id="r_test",
        user_id="u_test",
        session=object(),  # type: ignore[arg-type]
    )

    assert response.data == cached
