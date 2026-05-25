from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.modules.page_cache import save_cached
from app.modules.researchers.schemas import (
    ResearcherDetail,
    WorkbenchHiredResearcher,
    WorkbenchHotDocument,
    WorkbenchOverview,
    WorkbenchPublicRankItem,
    WorkbenchQuickAction,
)
from app.modules.researchers.service import ResearcherService, _workbench_overview_cache


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
async def test_async_get_workbench_overview_combines_main_entry_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workbench_overview_cache.clear()
    service = ResearcherService()

    async def fake_hired(*_args: object, **_kwargs: object) -> list[WorkbenchHiredResearcher]:
        return [
            WorkbenchHiredResearcher(
                researcher_id="r_b08dba104a",
                avatar_url=None,
                name="小市值轮动",
                summary="小市值策略研究员",
                status="active",
                tags=["小市值"],
                today_yield=1750.0,
                today_yield_rate=0.0018,
                month_yield_rate=-0.015,
                total_asset=985000.0,
                has_trading_account=True,
                level="LV.2",
            )
        ]

    async def fake_hot_documents(*_args: object, **_kwargs: object) -> list[WorkbenchHotDocument]:
        return [
            WorkbenchHotDocument(
                id="doc_1",
                title="今日复盘",
                summary="市场情绪回暖，小市值组合继续观察。",
                researcher_name="小市值轮动",
                create_time=datetime(2026, 4, 24, 9, 30),
                view_count=None,
                comment_count=None,
                metrics_ready=False,
            )
        ]

    async def fake_rankings(*_args: object, **_kwargs: object) -> list[WorkbenchPublicRankItem]:
        return [
            WorkbenchPublicRankItem(
                researcher_id="r_b08dba104a",
                name="小市值轮动",
                total_asset=1_008_000.0,
                today_yield_rate=0.008,
                month_yield_rate=0.018,
                risk_note="模拟盘",
            )
        ]

    monkeypatch.setattr(service, "async_list_workbench_hired", fake_hired)
    monkeypatch.setattr(service, "async_list_workbench_hot_documents", fake_hot_documents)
    monkeypatch.setattr(service, "async_list_public_rankings", fake_rankings)

    overview = await service.async_get_workbench_overview(object(), "u_demo", sort_by="today")  # type: ignore[arg-type]

    assert [item.name for item in overview.hired] == ["小市值轮动"]
    assert [item.title for item in overview.hot_documents] == ["今日复盘"]
    assert [item.total_asset for item in overview.rankings] == [1_008_000.0]
    assert overview.risk_disclaimer
    assert overview.partial_failures == []


@pytest.mark.asyncio
async def test_async_get_workbench_overview_reads_redis_snapshot_before_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workbench_overview_cache.clear()
    redis = FakeRedis()
    service = ResearcherService()
    cached = WorkbenchOverview(
        hired=[],
        hot_documents=[],
        rankings=[],
        quick_actions=[
            WorkbenchQuickAction(
                action_key="cached",
                title="缓存动作",
                description="来自 Redis",
            )
        ],
        risk_disclaimer="cached risk",
        partial_failures=[],
    )
    await save_cached(redis, "researchers:workbench:overview:u_demo:today", cached, ttl_seconds=120)

    monkeypatch.setattr(
        "app.modules.researchers.service.get_container",
        lambda: SimpleNamespace(redis=FakeRedisFactory(redis)),
    )

    async def fail_hired(*_args: object, **_kwargs: object) -> list[WorkbenchHiredResearcher]:
        raise AssertionError("Redis hit must not query hired researchers")

    monkeypatch.setattr(service, "async_list_workbench_hired", fail_hired)

    overview = await service.async_get_workbench_overview(object(), "u_demo", sort_by="today")  # type: ignore[arg-type]

    assert overview.risk_disclaimer == "cached risk"
    assert overview.quick_actions[0].action_key == "cached"


@pytest.mark.asyncio
async def test_async_get_workbench_overview_keeps_page_usable_when_optional_sections_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _workbench_overview_cache.clear()
    service = ResearcherService()

    async def fake_hired(*_args: object, **_kwargs: object) -> list[WorkbenchHiredResearcher]:
        return []

    async def fail_hot_documents(*_args: object, **_kwargs: object) -> list[WorkbenchHotDocument]:
        raise RuntimeError("document source unavailable")

    async def fail_rankings(*_args: object, **_kwargs: object) -> list[WorkbenchPublicRankItem]:
        raise RuntimeError("ranking source unavailable")

    monkeypatch.setattr(service, "async_list_workbench_hired", fake_hired)
    monkeypatch.setattr(service, "async_list_workbench_hot_documents", fail_hot_documents)
    monkeypatch.setattr(service, "async_list_public_rankings", fail_rankings)

    overview = await service.async_get_workbench_overview(object(), "u_demo", sort_by="today")  # type: ignore[arg-type]

    assert overview.hired == []
    assert overview.hot_documents == []
    assert overview.rankings == []
    assert overview.partial_failures == ["hot_documents", "rankings"]


@pytest.mark.asyncio
async def test_async_list_public_rankings_uses_trading_account_snapshot_pnl() -> None:
    service = ResearcherService()

    small_cap = SimpleNamespace(id="r_small", name="小市值轮动")
    neutral = SimpleNamespace(id="r_neutral", name="超短情绪")
    small_cap_account = SimpleNamespace(
        id="acct_small",
        total_asset=985000.0,
        available_cash=10000.0,
        holding_value=975000.0,
        daily_pnl=1750.0,
    )
    neutral_account = SimpleNamespace(
        id="acct_neutral",
        total_asset=1000000.0,
        available_cash=1000000.0,
        holding_value=0.0,
        daily_pnl=0.0,
    )

    class FakeResult:
        def all(self) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
            return [(small_cap, small_cap_account), (neutral, neutral_account)]

    class FakeSession:
        async def execute(self, *_args: object, **_kwargs: object) -> FakeResult:
            return FakeResult()

    async def fake_load_account_replays(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "acct_small": SimpleNamespace(daily_equity={"2000-01-01": 983250.0}),
            "acct_neutral": SimpleNamespace(daily_equity={"2000-01-01": 1000000.0}),
        }

    service._load_account_replays = fake_load_account_replays  # type: ignore[method-assign]

    rankings = await service.async_list_public_rankings(FakeSession(), sort_by="today")  # type: ignore[arg-type]

    assert [item.name for item in rankings] == ["小市值轮动", "超短情绪"]
    small_cap_rank = rankings[0]
    assert small_cap_rank.today_yield_rate == pytest.approx(1750.0 / (985000.0 - 1750.0))
    assert small_cap_rank.month_yield_rate == pytest.approx(-0.015)


@pytest.mark.asyncio
async def test_async_test_chat_falls_back_to_market_snapshot_when_llm_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ResearcherService()
    detail = ResearcherDetail(
        researcher_id="r_demo",
        name="情绪超短·阿发",
        title="超短研究员",
        style="情绪周期",
        status="active",
        today_pnl=0.0,
        win_rate_30d=0.0,
        level="资深",
        description="专注题材与涨停结构。",
        prompt="",
        visibility="public",
        published_version="v2",
        skills=[],
        knowledge_bases=[],
        mcp_servers=[],
        self_drive_tasks=[],
        created_at=datetime(2026, 5, 24),
        updated_at=datetime(2026, 5, 24),
    )

    class FakeLlm:
        is_configured = False

    async def fake_detail(*_args: object, **_kwargs: object) -> ResearcherDetail:
        return detail

    async def fake_run_sync(fn: object, *args: object, **_kwargs: object) -> str:
        return fn(*args)  # type: ignore[operator]

    monkeypatch.setattr(service, "async_get_researcher", fake_detail)
    monkeypatch.setattr("app.modules.researchers.service.get_llm_client", lambda: FakeLlm())
    monkeypatch.setattr("app.modules.researchers.service.run_sync", fake_run_sync)
    monkeypatch.setattr(
        "app.modules.researchers.service.get_limit_up_pool",
        lambda: [
            SimpleNamespace(name="测试龙头", symbol="000001", consecutive=3, amount=10_000_000),
        ],
    )
    monkeypatch.setattr(
        "app.modules.researchers.service.get_live_news_merged",
        lambda: [
            SimpleNamespace(title="测试快讯：半导体设备订单增长"),
        ],
    )

    result = await service.async_test_chat(object(), "r_demo", "半导体还能追吗？")  # type: ignore[arg-type]

    assert result.researcher_id == "r_demo"
    assert result.version_used == "v2"
    assert "半导体还能追吗" in result.answer
    assert "测试龙头(000001)3板" in result.answer
    assert "不构成投资建议" in result.answer


@pytest.mark.asyncio
async def test_async_list_public_rankings_uses_trading_account_view_pnl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ResearcherService()

    stale_winner = SimpleNamespace(id="r_stale", name="旧字段高收益")
    view_winner = SimpleNamespace(id="r_view", name="资金曲线高收益")
    stale_account = SimpleNamespace(
        id="acct_stale",
        total_asset=990000.0,
        available_cash=990000.0,
        holding_value=0.0,
        daily_pnl=50000.0,
    )
    view_account = SimpleNamespace(
        id="acct_view",
        total_asset=1005000.0,
        available_cash=1005000.0,
        holding_value=0.0,
        daily_pnl=-50000.0,
    )

    class FakeResult:
        def all(self) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
            return [(stale_winner, stale_account), (view_winner, view_account)]

    class FakeSession:
        async def execute(self, *_args: object, **_kwargs: object) -> FakeResult:
            return FakeResult()

    async def fake_load_account_replays(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {
            "acct_stale": SimpleNamespace(daily_equity={"2000-01-01": 1_000_000.0}),
            "acct_view": SimpleNamespace(daily_equity={"2000-01-01": 1_000_000.0}),
        }

    monkeypatch.setattr(service, "_load_account_replays", fake_load_account_replays)

    rankings = await service.async_list_public_rankings(FakeSession(), sort_by="today")  # type: ignore[arg-type]

    assert [item.name for item in rankings] == ["资金曲线高收益", "旧字段高收益"]
    assert rankings[0].today_yield_rate == pytest.approx(5000.0 / 1_000_000.0)
    assert rankings[1].today_yield_rate == pytest.approx(-10000.0 / 1_000_000.0)


def test_researcher_card_uses_trading_account_metrics_not_researcher_seed_fields() -> None:
    researcher = SimpleNamespace(
        id="r_small",
        avatar_url=None,
        name="小市值轮动",
        description="策略说明",
        status="active",
        tags=["小市值"],
        today_pnl=999999.0,
        win_rate_30d=0.88,
        level="LV.2",
    )
    account = SimpleNamespace(total_asset=985000.0, daily_pnl=1750.0)

    replay = SimpleNamespace(daily_equity={"2000-01-01": 983250.0})
    card = ResearcherService._researcher_to_hired_card(researcher, account, replay=replay)

    assert card.has_trading_account is True
    assert card.today_yield == 1750.0
    assert card.today_yield_rate == pytest.approx(1750.0 / (985000.0 - 1750.0))
    assert card.month_yield_rate == pytest.approx(-0.015)
    assert card.total_asset == 985000.0
    assert card.win_rate_30d is None
