from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.modules.news_analysis import router as news_router
from app.modules.news_analysis.schemas import (
    HotNewsRankItem,
    HotStockTag,
    NewsAiPanel,
    NewsAnalysisItem,
    NewsStockRelation,
    SentimentDistribution,
    StockNewsSummary,
)


def _fallback_panels() -> list[NewsAiPanel]:
    now = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    return [
        NewsAiPanel(
            panel_key="24h_digest",
            title="24小时热讯解读",
            summary="涨停池实时回补。",
            highlights=["涨停家数回升"],
            confidence=0.88,
            updated_at=now,
        ),
        NewsAiPanel(
            panel_key="hotspot_tracking",
            title="热点追踪",
            summary="半导体扩散。",
            highlights=["半导体涨停较多"],
            confidence=0.85,
            updated_at=now,
        ),
        NewsAiPanel(
            panel_key="macro_impact",
            title="宏观影响",
            summary="市场中性偏强。",
            highlights=["强势股增加"],
            confidence=0.82,
            updated_at=now,
        ),
        NewsAiPanel(
            panel_key="stock_interpretation",
            title="个股解读",
            summary="关注最高连板。",
            highlights=["龙头封单稳定"],
            confidence=0.86,
            updated_at=now,
        ),
    ]


@pytest.mark.asyncio
async def test_ai_panels_returns_cached_snapshot_without_live_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    fallback = _fallback_panels()

    async def fail_llm() -> list[NewsAiPanel]:
        raise AssertionError("AI panel page path must not call LLM")

    async def fake_run_sync(fetch: object) -> list[NewsAiPanel]:
        raise AssertionError("AI panel page path must not call live fallback")

    news_router.set_ai_panels_cache(fallback)
    monkeypatch.setattr(news_router.service, "generate_ai_panels_with_llm", fail_llm)
    monkeypatch.setattr(news_router, "run_sync", fake_run_sync)

    response = await news_router.ai_panels()

    assert response.data.total == 4
    assert response.data.items[0].panel_key == "24h_digest"
    assert response.data.items[1].summary == "半导体扩散。"


@pytest.mark.asyncio
async def test_news_analysis_all_returns_cached_snapshot_without_live_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    cached_feed = [
        NewsAnalysisItem(
            news_id="na_cached",
            category="flash",
            source="缓存",
            title="缓存资讯",
            summary="缓存资讯",
            content="缓存资讯",
            importance=3,
            is_important=False,
            publish_time=now,
        )
    ]
    cached_hot_stocks = [HotStockTag(stock_code="000001", stock_name="平安银行", heat=88, label="热股")]
    cached_hot_news = [
        HotNewsRankItem(
            rank=1,
            news_id="hn_cached",
            title="缓存热讯",
            source="缓存",
            publish_time=now,
            category="flash",
            heat_score=90,
        )
    ]

    news_router.set_news_analysis_cache(cached_feed, cached_hot_stocks, cached_hot_news)

    async def fail_run_sync(_func: object, *args: object, **kwargs: object) -> object:
        raise AssertionError("page aggregate endpoint must not live-fetch news analysis data")

    monkeypatch.setattr(news_router, "run_sync", fail_run_sync)

    response = await news_router.news_analysis_all()

    assert response.data.feed == cached_feed
    assert response.data.hot_stocks == cached_hot_stocks
    assert response.data.hot_news == cached_hot_news


@pytest.mark.asyncio
async def test_stock_summary_is_derived_from_cached_feed_without_live_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    news_router._stock_summary_cache.clear()
    now = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    cached_feed = [
        NewsAnalysisItem(
            news_id="na_stock",
            category="flash",
            source="缓存",
            title="平安银行增长提速",
            summary="缓存资讯",
            content="缓存资讯",
            importance=4,
            is_important=True,
            publish_time=now,
            stock_relations=[NewsStockRelation(stock_code="000001", stock_name="平安银行")],
        )
    ]
    news_router.set_news_analysis_cache(cached_feed, [], [])

    async def fail_run_sync(_func: object, *args: object, **kwargs: object) -> object:
        raise AssertionError("stock summary endpoint must not live-fetch stock news")

    monkeypatch.setattr(news_router, "run_sync", fail_run_sync)

    response = await news_router.by_stock_summary("000001")

    assert response.data.stock_code == "000001"
    assert response.data.stock_name == "平安银行"
    assert response.data.related_news_count == 1
    assert response.data.sentiment_distribution.bullish == 1


@pytest.mark.asyncio
async def test_stock_summary_prefers_cached_summary_without_live_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    news_router._stock_summary_cache.clear()
    now = datetime(2026, 5, 24, 10, 0, tzinfo=UTC)
    cached_summary = StockNewsSummary(
        stock_code="000002",
        stock_name="万科A",
        conclusion="后台缓存摘要",
        related_news_count=7,
        sentiment_distribution=SentimentDistribution(bullish=5, neutral=2, bearish=0),
        related_themes=["地产链"],
        avg_confidence=0.91,
        latest_publish_time=now,
    )
    news_router.set_news_analysis_cache([], [], [])
    news_router.set_stock_summary_cache(cached_summary)

    async def fail_run_sync(_func: object, *args: object, **kwargs: object) -> object:
        raise AssertionError("stock summary endpoint must read cached summary only")

    monkeypatch.setattr(news_router, "run_sync", fail_run_sync)

    response = await news_router.by_stock_summary("000002")

    assert response.data == cached_summary
