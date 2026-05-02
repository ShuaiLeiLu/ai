"""
盘前速览路由

页面数据接口只读 Redis 快照；AKShare 由后台刷新任务定时写入快照。
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.core.container import get_container
from app.modules.preopen.schemas import (
    AiDigest,
    AnomalyOverview,
    HotNewsItem,
    IndustryBoardItem,
    LimitUpLadderItem,
    MarketIndicator,
    PreopenAllData,
    StockRankItem,
    TrendOverview,
)
from app.modules.preopen.service import PreopenService
from app.modules.preopen import snapshots
from app.modules.preopen.snapshot_cache import load_snapshot_or_empty
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/preopen", tags=["preopen"])
service = PreopenService()


@router.get("/all")
async def preopen_all() -> ApiResponse[PreopenAllData]:
    """聚合接口 —— 一次请求返回盘前速览全量快照数据。"""
    redis = get_container().redis.get_client()
    (
        hot_news_items,
        indicator_items,
        anomaly_data,
        trend_data,
        ladder_items,
        board_items,
        rank_up_items,
        rank_down_items,
    ) = await asyncio.gather(
        load_snapshot_or_empty(redis, snapshots.HOT_NEWS),
        load_snapshot_or_empty(redis, snapshots.MARKET_INDICATORS),
        load_snapshot_or_empty(redis, snapshots.ANOMALIES),
        load_snapshot_or_empty(redis, snapshots.TRENDS),
        load_snapshot_or_empty(redis, snapshots.LIMIT_UP_LADDER),
        load_snapshot_or_empty(redis, snapshots.INDUSTRY_BOARDS),
        load_snapshot_or_empty(redis, snapshots.STOCK_RANK_UP),
        load_snapshot_or_empty(redis, snapshots.STOCK_RANK_DOWN),
    )
    data = PreopenAllData(
        hot_news=hot_news_items,
        market_indicators=indicator_items,
        anomalies=anomaly_data,
        trends=trend_data,
        limit_up_ladder=ladder_items,
        industry_boards=board_items,
        stock_rank_up=rank_up_items,
        stock_rank_down=rank_down_items,
    )
    return ApiResponse(data=data)


@router.get("/hot-news")
async def hot_news() -> ApiResponse[ListResponse[HotNewsItem]]:
    redis = get_container().redis.get_client()
    items = await load_snapshot_or_empty(redis, snapshots.HOT_NEWS)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/ai-digest")
async def ai_digest() -> ApiResponse[AiDigest]:
    """盘前 AI 解读 —— 仅返回真实 LLM 分析结果。"""
    data = await service.generate_ai_digest_with_llm()
    return ApiResponse(data=data)


@router.get("/market-indicators")
async def market_indicators() -> ApiResponse[ListResponse[MarketIndicator]]:
    redis = get_container().redis.get_client()
    items = await load_snapshot_or_empty(redis, snapshots.MARKET_INDICATORS)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/anomalies")
async def anomalies() -> ApiResponse[AnomalyOverview]:
    redis = get_container().redis.get_client()
    data = await load_snapshot_or_empty(redis, snapshots.ANOMALIES)
    return ApiResponse(data=data)


@router.get("/trends")
async def trends() -> ApiResponse[TrendOverview]:
    redis = get_container().redis.get_client()
    data = await load_snapshot_or_empty(redis, snapshots.TRENDS)
    return ApiResponse(data=data)


@router.get("/limit-up-ladder")
async def limit_up_ladder() -> ApiResponse[ListResponse[LimitUpLadderItem]]:
    redis = get_container().redis.get_client()
    items = await load_snapshot_or_empty(redis, snapshots.LIMIT_UP_LADDER)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/industry-boards")
async def industry_boards() -> ApiResponse[ListResponse[IndustryBoardItem]]:
    redis = get_container().redis.get_client()
    items = await load_snapshot_or_empty(redis, snapshots.INDUSTRY_BOARDS)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/stock-rank")
async def stock_rank(direction: str = "up") -> ApiResponse[ListResponse[StockRankItem]]:
    redis = get_container().redis.get_client()
    spec = snapshots.STOCK_RANK_DOWN if direction == "down" else snapshots.STOCK_RANK_UP
    items = await load_snapshot_or_empty(redis, spec)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
