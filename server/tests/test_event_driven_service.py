from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import HTTPException
import pytest

from app.integrations.akshare.client import IndustryBoard, LimitUpStock, LiveNewsItem
from app.modules.event_driven import service as event_service
from app.modules.event_driven.service import EventDrivenService, MarketSnapshot


def _stock(
    symbol: str,
    name: str,
    industry: str,
    *,
    consecutive: int = 1,
    break_count: int = 0,
) -> LimitUpStock:
    return LimitUpStock(
        symbol=symbol,
        name=name,
        change_pct=10.0,
        price=12.3,
        amount=1_200_000_000,
        turnover_ratio=8.5,
        seal_amount=180_000_000,
        first_seal_time="09:35:12",
        last_seal_time="14:55:01",
        break_count=break_count,
        consecutive=consecutive,
        industry=industry,
    )


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        pool=[
            _stock("688012", "中微公司", "半导体", consecutive=2),
            _stock("002371", "北方华创", "半导体设备", consecutive=1, break_count=1),
            _stock("002463", "沪电股份", "PCB", consecutive=3),
            _stock("300308", "中际旭创", "光通信", consecutive=1),
        ],
        boards=[
            IndustryBoard(
                name="半导体",
                change_pct=3.2,
                total_volume=100,
                total_amount=250,
                net_inflow=18,
                rise_count=72,
                fall_count=8,
                leading_stock="中微公司",
                leading_stock_pct=10.0,
            )
        ],
        news=[
            LiveNewsItem(
                title="工信部推动半导体设备国产化",
                content="政策继续支持关键设备和材料突破。",
                publish_time="2026-05-24 10:00:00",
                url="",
                source="同花顺",
            )
        ],
        generated_at=datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc),
    )


def test_list_themes_uses_market_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(event_service, "_load_market_snapshot", _snapshot)

    themes = EventDrivenService().list_themes()
    semiconductor = next(item for item in themes if item.id == "semiconductor")

    assert semiconductor.limit_up_count == 2
    assert semiconductor.event_count >= 1
    assert semiconductor.status == "today_hot"
    assert semiconductor.rank == 1


def test_get_theme_builds_detail_from_market_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(event_service, "_load_market_snapshot", _snapshot)

    detail = EventDrivenService().get_theme("semiconductor")

    assert detail is not None
    assert detail.limit_up_count == 2
    assert detail.they_say.summary.startswith("当日涨停 4 家")
    assert detail.event_chain.past_events[0].source == "同花顺"
    assert detail.event_chain.core_target_groups[0].items[0].name == "中微公司"
    assert any(gap.direction == "overvalued" for gap in detail.expectation_gaps)


def test_empty_market_sources_do_not_fall_back_to_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        event_service,
        "_load_market_snapshot",
        lambda: MarketSnapshot(pool=[], boards=[], news=[], generated_at=datetime(2026, 5, 24, tzinfo=timezone.utc)),
    )

    themes = EventDrivenService().list_themes()
    detail = EventDrivenService().get_theme("semiconductor")

    assert themes == []
    assert detail is None


def test_event_driven_page_reads_cached_snapshot_without_live_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EventDrivenService()
    service.set_cached_market_snapshot(_snapshot())

    def fail_live_snapshot() -> MarketSnapshot:
        raise AssertionError("page read path must not load external market snapshot")

    monkeypatch.setattr(event_service, "_load_market_snapshot", fail_live_snapshot)

    themes = service.list_themes()
    detail = service.get_theme("semiconductor")
    they_say = service.they_say()

    assert themes[0].id == "semiconductor"
    assert detail is not None
    assert detail.limit_up_count == 2
    assert they_say.summary.startswith("当日涨停 4 家")


def test_event_driven_service_restores_cached_snapshot_from_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    service = EventDrivenService(cache_only=True)
    service.set_cached_market_snapshot_payload(_snapshot().to_cache_payload())

    def fail_live_snapshot() -> MarketSnapshot:
        raise AssertionError("cache-only service must not load external market snapshot")

    monkeypatch.setattr(event_service, "_load_market_snapshot", fail_live_snapshot)

    themes = service.list_themes()

    assert themes[0].id == "semiconductor"


def test_unmatched_theme_is_not_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(event_service, "_load_market_snapshot", _snapshot)

    detail = EventDrivenService().get_theme("education")

    assert detail is None


@pytest.mark.asyncio
async def test_unlock_deducts_battery_and_writes_ledger(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id="u_1", membership_level="普通用户", battery_balance=260)
    ledger_items: list[object] = []

    class FakeUserRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _user_id: str) -> object:
            return user

        async def update_battery(self, user_obj: object, delta: int) -> object:
            user_obj.battery_balance += delta
            return user_obj

    class FakeSession:
        def add(self, item: object) -> None:
            ledger_items.append(item)

        async def commit(self) -> None:
            pass

    async def no_existing_unlock(_service: object, _session: object, _user_id: str) -> bool:
        return False

    monkeypatch.setattr(event_service, "UserRepository", FakeUserRepo)
    monkeypatch.setattr(EventDrivenService, "_has_today_unlock", no_existing_unlock)

    result = await EventDrivenService().async_unlock(FakeSession(), "u_1")  # type: ignore[arg-type]

    assert result.success is True
    assert result.battery_balance == 60
    assert user.battery_balance == 60
    assert len(ledger_items) == 1
    assert ledger_items[0].change == -200
    assert ledger_items[0].balance_after == 60
    assert ledger_items[0].reason == "题材掘金单日解锁"


@pytest.mark.asyncio
async def test_unlock_rejects_when_battery_insufficient(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id="u_1", membership_level="普通用户", battery_balance=26)

    class FakeUserRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _user_id: str) -> object:
            return user

    async def no_existing_unlock(_service: object, _session: object, _user_id: str) -> bool:
        return False

    monkeypatch.setattr(event_service, "UserRepository", FakeUserRepo)
    monkeypatch.setattr(EventDrivenService, "_has_today_unlock", no_existing_unlock)

    with pytest.raises(HTTPException) as exc:
        await EventDrivenService().async_unlock(object(), "u_1")  # type: ignore[arg-type]

    assert exc.value.status_code == 402
    assert "算力不足" in exc.value.detail


@pytest.mark.asyncio
async def test_unlock_does_not_deduct_for_vip(monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(id="u_1", membership_level="VIP1", battery_balance=26)
    ledger_items: list[object] = []

    class FakeUserRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_id(self, _user_id: str) -> object:
            return user

    class FakeSession:
        def add(self, item: object) -> None:
            ledger_items.append(item)

    monkeypatch.setattr(event_service, "UserRepository", FakeUserRepo)

    result = await EventDrivenService().async_unlock(FakeSession(), "u_1")  # type: ignore[arg-type]

    assert result.success is True
    assert result.battery_balance == 26
    assert ledger_items == []
