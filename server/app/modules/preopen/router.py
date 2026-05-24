"""
盘前速览路由

页面数据接口优先读取 Redis 快照；快照缺失时实时调用 AKShare 聚合兜底。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TypeVar

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_dependency, get_optional_session
from app.core.container import get_container
from app.integrations.akshare.client import run_sync
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
from app.modules.preopen.skill_service import (
    run_preopen_chain,
    stream_preopen_chain,
)
from app.modules.preopen import snapshots
from app.modules.preopen.snapshot_cache import SnapshotSpec, load_snapshot
from app.schemas.common import ApiResponse, ListResponse

logger = logging.getLogger(__name__)
T = TypeVar("T")

router = APIRouter(prefix="/preopen", tags=["preopen"])
service = PreopenService()


async def _load_snapshot_or_empty(redis: object, spec: SnapshotSpec[T]) -> T:
    try:
        data = await load_snapshot(redis, spec)
        return data if data is not None else spec.empty_factory()
    except Exception:
        logger.info("[盘前速览] 快照不可用，使用实时数据兜底：%s", spec.name)
        return spec.empty_factory()


async def _load_list_or_live(redis: object, spec: SnapshotSpec[list[T]], fetch: Callable[[], list[T]]) -> list[T]:
    items = await _load_snapshot_or_empty(redis, spec)
    if items:
        return items
    return await run_sync(fetch)


async def _load_anomalies_or_live(redis: object) -> AnomalyOverview:
    data = await _load_snapshot_or_empty(redis, snapshots.ANOMALIES)
    if data.tail_session_moves or data.severe_volatility:
        return data
    return await run_sync(service.get_anomalies)


async def _load_trends_or_live(redis: object) -> TrendOverview:
    data = await _load_snapshot_or_empty(redis, snapshots.TRENDS)
    if data.series and any(series.points for series in data.series):
        return data
    return await run_sync(service.get_trends)


@router.get("/all")
async def preopen_all(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[PreopenAllData]:
    """聚合接口 —— 一次请求返回盘前速览全量数据，快照缺失时实时采集。"""
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
        _load_list_or_live(redis, snapshots.HOT_NEWS, service.list_hot_news),
        _load_list_or_live(redis, snapshots.MARKET_INDICATORS, service.list_market_indicators),
        _load_anomalies_or_live(redis),
        _load_trends_or_live(redis),
        _load_list_or_live(redis, snapshots.LIMIT_UP_LADDER, service.list_limit_up_ladder),
        _load_list_or_live(redis, snapshots.INDUSTRY_BOARDS, service.list_industry_boards),
        _load_list_or_live(redis, snapshots.STOCK_RANK_UP, lambda: service.list_stock_rank("up")),
        _load_list_or_live(redis, snapshots.STOCK_RANK_DOWN, lambda: service.list_stock_rank("down")),
    )
    if session is not None:
        try:
            trend_data = await service.async_get_trends(session)
            await session.commit()
        except Exception:
            await session.rollback()
            trend_data = trend_data or service.get_trends()
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
    items = await _load_list_or_live(redis, snapshots.HOT_NEWS, service.list_hot_news)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/ai-digest")
async def ai_digest() -> ApiResponse[AiDigest]:
    """盘前 AI 解读 —— LLM 优先，未配置或失败时返回 AkShare 结构化研判。"""
    try:
        data = await service.generate_ai_digest_with_llm()
    except Exception:
        logger.warning("[盘前速览] LLM 解读不可用，回退到 AkShare 结构化研判", exc_info=True)
        data = await run_sync(service.get_ai_digest)
    return ApiResponse(data=data)


@router.get("/ai-digest-v2/stream")
async def ai_digest_v2_stream(
    session: AsyncSession = Depends(db_session_dependency),
) -> StreamingResponse:
    """盘前 AI 解读 v2 —— SSE 流式输出 skill chain 各阶段事件。

    事件类型:
      - started:整体启动
      - skill_started:某 skill 开始
      - skill_chunk:synthesis 类 skill 流式文本片段
      - skill_completed:某 skill 完成
      - skill_failed:某 skill 失败
      - done:整体完成
      - persisted:digest 已落库
      - error:服务级错误
    """
    return StreamingResponse(
        stream_preopen_chain(session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/ai-digest-v2")
async def ai_digest_v2(
    session: AsyncSession = Depends(db_session_dependency),
) -> ApiResponse[dict]:
    """盘前 AI 解读 v2 —— 非流式版本(供测试 / 调度任务调用)。"""
    data = await run_preopen_chain(session)
    await session.commit()
    return ApiResponse(data=data)


@router.get("/market-indicators")
async def market_indicators() -> ApiResponse[ListResponse[MarketIndicator]]:
    redis = get_container().redis.get_client()
    items = await _load_list_or_live(redis, snapshots.MARKET_INDICATORS, service.list_market_indicators)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/anomalies")
async def anomalies() -> ApiResponse[AnomalyOverview]:
    redis = get_container().redis.get_client()
    data = await _load_anomalies_or_live(redis)
    return ApiResponse(data=data)


@router.get("/trends")
async def trends(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TrendOverview]:
    if session is not None:
        try:
            data = await service.async_get_trends(session)
            await session.commit()
            return ApiResponse(data=data)
        except Exception:
            await session.rollback()
    redis = get_container().redis.get_client()
    data = await _load_trends_or_live(redis)
    return ApiResponse(data=data)


@router.get("/limit-up-ladder")
async def limit_up_ladder() -> ApiResponse[ListResponse[LimitUpLadderItem]]:
    redis = get_container().redis.get_client()
    items = await _load_list_or_live(redis, snapshots.LIMIT_UP_LADDER, service.list_limit_up_ladder)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/industry-boards")
async def industry_boards() -> ApiResponse[ListResponse[IndustryBoardItem]]:
    redis = get_container().redis.get_client()
    items = await _load_list_or_live(redis, snapshots.INDUSTRY_BOARDS, service.list_industry_boards)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/stock-rank")
async def stock_rank(direction: str = "up") -> ApiResponse[ListResponse[StockRankItem]]:
    redis = get_container().redis.get_client()
    spec = snapshots.STOCK_RANK_DOWN if direction == "down" else snapshots.STOCK_RANK_UP
    items = await _load_list_or_live(redis, spec, lambda: service.list_stock_rank(direction))
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
