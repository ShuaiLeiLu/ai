"""
资讯分析路由

页面读接口只返回已缓存快照；后台刷新任务负责回源采集。
"""
from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter
from pydantic import TypeAdapter

from app.core.container import get_container
from app.integrations.akshare.client import run_sync
from app.modules.page_cache import load_cached, save_cached
from app.modules.news_analysis.schemas import (
    HotNewsRankItem,
    HotStockTag,
    NewsAiPanel,
    NewsAnalysisAllData,
    NewsAnalysisItem,
    NewsFeedCategory,
    SentimentDistribution,
    StockNewsSummary,
)
from app.modules.news_analysis.service import NewsAnalysisService
from app.schemas.common import ApiResponse, ListResponse

logger = logging.getLogger(__name__)

# ── 聚合接口缓存 ──
_all_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}
_ai_panels_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}
_stock_summary_cache: dict[str, dict[str, Any]] = {}
_ALL_CACHE_TTL = 60  # 60 秒
_AI_PANELS_CACHE_TTL = 300  # 5 分钟
_STOCK_SUMMARY_CACHE_TTL = 300  # 5 分钟
_STOCK_SUMMARY_REFRESH_LIMIT = 10
_ALL_CACHE_NAME = "news-analysis:all"
_AI_PANELS_CACHE_NAME = "news-analysis:ai-panels"
_STOCK_SUMMARY_CACHE_PREFIX = "news-analysis:stock-summary:"
_ALL_CACHE_ADAPTER = TypeAdapter(NewsAnalysisAllData)
_AI_PANELS_CACHE_ADAPTER = TypeAdapter(list[NewsAiPanel])
_STOCK_SUMMARY_CACHE_ADAPTER = TypeAdapter(StockNewsSummary)

router = APIRouter(prefix="/news-analysis", tags=["news-analysis"])
service = NewsAnalysisService()


def set_news_analysis_cache(
    feed_items: list[NewsAnalysisItem],
    hot_stocks_items: list[HotStockTag],
    hot_news_items: list[HotNewsRankItem],
    *,
    ttl_seconds: int = _ALL_CACHE_TTL,
) -> NewsAnalysisAllData:
    data = NewsAnalysisAllData(
        feed=feed_items,
        hot_stocks=hot_stocks_items,
        hot_news=hot_news_items,
    )
    _all_cache["data"] = data
    _all_cache["expires_at"] = time.monotonic() + ttl_seconds
    return data


def set_ai_panels_cache(
    items: list[NewsAiPanel],
    *,
    ttl_seconds: int = _AI_PANELS_CACHE_TTL,
) -> list[NewsAiPanel]:
    _ai_panels_cache["data"] = items
    _ai_panels_cache["expires_at"] = time.monotonic() + ttl_seconds
    return items


def set_stock_summary_cache(
    item: StockNewsSummary,
    *,
    ttl_seconds: int = _STOCK_SUMMARY_CACHE_TTL,
) -> StockNewsSummary:
    _stock_summary_cache[item.stock_code] = {
        "data": item,
        "expires_at": time.monotonic() + ttl_seconds,
    }
    return item


def _stock_summary_cache_name(stock_code: str) -> str:
    return f"{_STOCK_SUMMARY_CACHE_PREFIX}{stock_code.strip()}"


async def refresh_news_analysis_cache() -> NewsAnalysisAllData:
    feed_items = await run_sync(service.list_feed)
    hot_stocks_items = await run_sync(service.list_hot_stocks)
    hot_news_items = await run_sync(service.list_hot_news)
    data = set_news_analysis_cache(feed_items, hot_stocks_items, hot_news_items)
    redis = None
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, _ALL_CACHE_NAME, data, ttl_seconds=_ALL_CACHE_TTL * 10)
    except Exception:
        logger.warning("[资讯分析] Redis 缓存写入失败", exc_info=True)

    for stock in hot_stocks_items[:_STOCK_SUMMARY_REFRESH_LIMIT]:
        try:
            summary = await run_sync(service.get_stock_summary, stock.stock_code)
            if summary.stock_name == summary.stock_code and stock.stock_name:
                summary = summary.model_copy(update={"stock_name": stock.stock_name})
            set_stock_summary_cache(summary)
            if redis is not None:
                await save_cached(
                    redis,
                    _stock_summary_cache_name(stock.stock_code),
                    summary,
                    ttl_seconds=_STOCK_SUMMARY_CACHE_TTL * 4,
                )
        except Exception:
            logger.warning("[资讯分析] 股票摘要缓存刷新失败：%s", stock.stock_code, exc_info=True)
    return data


async def refresh_ai_panels_cache() -> list[NewsAiPanel]:
    try:
        items = await service.generate_ai_panels_with_llm()
    except Exception:
        logger.warning("[资讯分析] LLM 面板刷新不可用，回退到 AkShare 结构化分析", exc_info=True)
        items = await run_sync(service.list_ai_panels)
    items = set_ai_panels_cache(items)
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, _AI_PANELS_CACHE_NAME, items, ttl_seconds=_AI_PANELS_CACHE_TTL * 4)
    except Exception:
        logger.warning("[资讯分析] AI 面板 Redis 缓存写入失败", exc_info=True)
    return items


def _cached_all_data() -> NewsAnalysisAllData:
    now = time.monotonic()
    data = _all_cache.get("data")
    if isinstance(data, NewsAnalysisAllData) and now < float(_all_cache.get("expires_at") or 0):
        return data
    return NewsAnalysisAllData(feed=[], hot_stocks=[], hot_news=[])


async def _cached_all_data_async() -> NewsAnalysisAllData:
    try:
        redis = get_container().redis.get_client()
        data = await load_cached(redis, _ALL_CACHE_NAME, _ALL_CACHE_ADAPTER)
        if data is not None:
            set_news_analysis_cache(data.feed, data.hot_stocks, data.hot_news)
            return data
    except Exception:
        logger.warning("[资讯分析] Redis 缓存读取失败", exc_info=True)
    return _cached_all_data()


def _cached_ai_panels() -> list[NewsAiPanel]:
    now = time.monotonic()
    data = _ai_panels_cache.get("data")
    if isinstance(data, list) and now < float(_ai_panels_cache.get("expires_at") or 0):
        return data
    return []


async def _cached_ai_panels_async() -> list[NewsAiPanel]:
    try:
        redis = get_container().redis.get_client()
        data = await load_cached(redis, _AI_PANELS_CACHE_NAME, _AI_PANELS_CACHE_ADAPTER)
        if data is not None:
            set_ai_panels_cache(data)
            return data
    except Exception:
        logger.warning("[资讯分析] AI 面板 Redis 缓存读取失败", exc_info=True)
    return _cached_ai_panels()


async def _cached_stock_summary_async(
    stock_code: str,
    feed_items: list[NewsAnalysisItem],
) -> StockNewsSummary:
    normalized = stock_code.strip()
    try:
        redis = get_container().redis.get_client()
        data = await load_cached(redis, _stock_summary_cache_name(normalized), _STOCK_SUMMARY_CACHE_ADAPTER)
        if data is not None:
            set_stock_summary_cache(data)
            return data
    except Exception:
        logger.warning("[资讯分析] 股票摘要 Redis 缓存读取失败：%s", normalized, exc_info=True)

    cached = _stock_summary_cache.get(normalized)
    if cached is not None:
        data = cached.get("data")
        expires_at = float(cached.get("expires_at") or 0)
        if isinstance(data, StockNewsSummary) and time.monotonic() < expires_at:
            return data

    return _stock_summary_from_cached_feed(normalized, feed_items)


def _filter_feed(
    items: list[NewsAnalysisItem],
    *,
    category: NewsFeedCategory,
    important_only: bool,
    stock_code: str | None,
) -> list[NewsAnalysisItem]:
    stock = (stock_code or "").strip()
    filtered: list[NewsAnalysisItem] = []
    for item in items:
        if category != "all" and item.category != category:
            continue
        if important_only and not item.is_important:
            continue
        if stock and not any(rel.stock_code == stock or stock in rel.stock_name for rel in item.stock_relations):
            continue
        filtered.append(item)
    return filtered


@router.get("/feed")
async def feed(
    category: NewsFeedCategory = "all",
    important_only: bool = False,
    stock_code: str | None = None,
) -> ApiResponse[ListResponse[NewsAnalysisItem]]:
    data = await _cached_all_data_async()
    items = _filter_feed(
        data.feed,
        category=category,
        important_only=important_only,
        stock_code=stock_code,
    )
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/ai-panels")
async def ai_panels() -> ApiResponse[ListResponse[NewsAiPanel]]:
    """AI 智能分析面板 —— 返回后台已生成的缓存快照。"""
    items = await _cached_ai_panels_async()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/hot-stocks")
async def hot_stocks() -> ApiResponse[ListResponse[HotStockTag]]:
    items = (await _cached_all_data_async()).hot_stocks
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/hot-news")
async def hot_news() -> ApiResponse[ListResponse[HotNewsRankItem]]:
    items = (await _cached_all_data_async()).hot_news
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/by-stock/{stock_code}/summary")
async def by_stock_summary(stock_code: str) -> ApiResponse[StockNewsSummary]:
    all_data = await _cached_all_data_async()
    data = await _cached_stock_summary_async(stock_code, all_data.feed)
    return ApiResponse(data=data)


@router.get("/all")
async def news_analysis_all() -> ApiResponse[NewsAnalysisAllData]:
    """聚合接口 —— 一次请求返回资讯分析全量缓存快照。"""
    return ApiResponse(data=await _cached_all_data_async())


def _stock_summary_from_cached_feed(stock_code: str, feed_items: list[NewsAnalysisItem]) -> StockNewsSummary:
    normalized = stock_code.strip()
    related = [
        item
        for item in feed_items
        if any(rel.stock_code == normalized or normalized in rel.stock_name for rel in item.stock_relations)
    ]
    stock_name = normalized
    for item in related:
        relation = next(
            (rel for rel in item.stock_relations if rel.stock_code == normalized or normalized in rel.stock_name),
            None,
        )
        if relation is not None:
            stock_name = relation.stock_name
            break

    sentiment = SentimentDistribution()
    themes: set[str] = set()
    for item in related:
        text = f"{item.title} {item.summary} {item.content}"
        if any(word in text for word in ("涨", "增长", "突破", "新高", "利好")):
            sentiment.bullish += 1
        elif any(word in text for word in ("跌", "下降", "利空", "风险", "下跌")):
            sentiment.bearish += 1
        else:
            sentiment.neutral += 1
        themes.update(theme.theme_name for theme in item.theme_relations)

    if not related:
        conclusion = "暂无该股票的关联资讯，建议关注热门题材联动。"
    elif sentiment.bullish > sentiment.bearish:
        conclusion = "关联资讯整体偏积极，关注成交持续性与业绩兑现。"
    elif sentiment.bearish > sentiment.bullish:
        conclusion = "关联资讯偏谨慎，建议观察风险释放信号。"
    else:
        conclusion = "关联资讯情绪中性，关注催化事件。"

    latest_time = max((item.publish_time for item in related), default=None)
    return StockNewsSummary(
        stock_code=normalized,
        stock_name=stock_name,
        conclusion=conclusion,
        related_news_count=len(related),
        sentiment_distribution=sentiment,
        related_themes=sorted(themes),
        avg_confidence=0.80 if related else 0.0,
        latest_publish_time=latest_time,
    )
