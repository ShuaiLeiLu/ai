from __future__ import annotations

import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.modules.preopen import snapshots
from app.modules.preopen import router as preopen_router
from app.modules.preopen.service import PreopenService
from app.modules.preopen.schemas import AiDigest, AnomalyItem, HotNewsItem
from app.modules.preopen.router import _load_list_or_live
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


def test_ai_digest_parser_accepts_richer_workflow_fields() -> None:
    reply = json.dumps(
        {
            "headline": "新闻催化科技线升温",
            "sentiment": "bullish",
            "key_points": ["涨停家数回升", "连板高度打开"],
            "news_drivers": ["算力订单落地"],
            "opportunity_sectors": ["算力", "半导体"],
            "risk_sectors": ["高位地产"],
            "intraday_watch": ["观察算力涨停是否扩散"],
            "simulation_plan": ["只在板块共振时开仓"],
        },
        ensure_ascii=False,
    )

    digest = PreopenService._parse_ai_digest_response(reply)

    assert digest is not None
    assert digest.news_drivers == ["算力订单落地"]
    assert digest.opportunity_sectors == ["算力", "半导体"]
    assert digest.intraday_watch == ["观察算力涨停是否扩散"]
    assert digest.report_title
    assert len(digest.report_sections) >= 6
    assert digest.report_sections[0].title.startswith("一、先抛观点")


def test_trends_fallback_only_returns_real_latest_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.modules.preopen.service.get_limit_up_pool",
        lambda: [
            type("LimitItem", (), {"consecutive": 2})(),
            type("LimitItem", (), {"consecutive": 1})(),
        ],
    )
    monkeypatch.setattr("app.modules.preopen.service.get_limit_down_pool", lambda: [object()])

    trends = PreopenService().get_trends()

    assert trends.window_days == 1
    assert all(len(series.points) == 1 for series in trends.series)
    assert trends.series[0].points[0].value == 2
    assert trends.series[1].points[0].value == 1
    assert trends.series[2].points[0].value == 1


def test_anomaly_item_accepts_risk_prompt_fields() -> None:
    item = AnomalyItem(
        symbol="000001",
        name="平安银行",
        category="severe-volatility",
        change_pct=-9.8,
        turnover_ratio=12.3,
        risk_tags=["abnormal_volatility"],
        note="跌停，换手率 12.3%",
        risk_type="交易所异常波动风险",
        risk_window="连续10/30个交易日",
        is_new=True,
    )

    assert item.risk_type == "交易所异常波动风险"
    assert item.risk_window == "连续10/30个交易日"
    assert item.is_new is True


def test_trends_builds_real_multi_day_series_from_snapshots() -> None:
    rows = [
        SimpleNamespace(
            trade_date=date(2026, 4, 29),
            limit_up_count=45,
            limit_down_count=8,
            consecutive_limit_up_count=12,
        ),
        SimpleNamespace(
            trade_date=date(2026, 4, 30),
            limit_up_count=52,
            limit_down_count=5,
            consecutive_limit_up_count=18,
        ),
    ]

    trends = PreopenService._trend_overview_from_snapshots(rows, requested_days=15)  # type: ignore[arg-type]

    assert trends.window_days == 2
    assert [point.value for point in trends.series[0].points] == [45, 52]
    assert [point.trade_date for point in trends.series[1].points] == [
        date(2026, 4, 29),
        date(2026, 4, 30),
    ]


@pytest.mark.asyncio
async def test_empty_preopen_snapshot_falls_back_to_live_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    item = _hot_news_item("实时快讯")

    async def fake_run_sync(fetch: object) -> list[HotNewsItem]:
        assert callable(fetch)
        return [item]

    monkeypatch.setattr(preopen_router, "run_sync", fake_run_sync)

    loaded = await _load_list_or_live(FakeRedis(), snapshots.HOT_NEWS, lambda: [item])

    assert loaded == [item]


@pytest.mark.asyncio
async def test_ai_digest_endpoint_falls_back_when_llm_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fallback = AiDigest(
        digest_id="digest_fallback",
        headline="盘前情绪中性",
        interval_start=datetime(2026, 5, 24, 9, 0, tzinfo=UTC),
        interval_end=datetime(2026, 5, 24, 10, 0, tzinfo=UTC),
        generated_at=datetime(2026, 5, 24, 10, 0, tzinfo=UTC),
        sentiment="neutral",
        key_points=["涨停池实时回补"],
        news_drivers=[],
        opportunity_sectors=["半导体"],
        risk_sectors=[],
        intraday_watch=[],
        simulation_plan=[],
    )

    async def fail_llm() -> AiDigest:
        raise RuntimeError("llm unavailable")

    async def fake_run_sync(fetch: object) -> AiDigest:
        assert callable(fetch)
        return fallback

    monkeypatch.setattr(preopen_router.service, "generate_ai_digest_with_llm", fail_llm)
    monkeypatch.setattr(preopen_router.service, "get_ai_digest", lambda: fallback)
    monkeypatch.setattr(preopen_router, "run_sync", fake_run_sync)

    response = await preopen_router.ai_digest()

    assert response.data == fallback
