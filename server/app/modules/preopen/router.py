"""
盘前速览路由

页面数据接口只读 Redis 快照；AKShare 由后台刷新任务定时写入快照。
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import db_session_dependency, get_optional_session
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
from app.modules.preopen.skill_service import (
    run_preopen_chain,
    stream_preopen_chain,
)
from app.modules.preopen import snapshots
from app.modules.preopen.snapshot_cache import load_snapshot_or_empty
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/preopen", tags=["preopen"])
service = PreopenService()


@router.get("/all")
async def preopen_all(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[PreopenAllData]:
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
    items = await load_snapshot_or_empty(redis, snapshots.HOT_NEWS)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/ai-digest")
async def ai_digest() -> ApiResponse[AiDigest]:
    """盘前 AI 解读 —— 仅返回真实 LLM 分析结果。"""
    data = await service.generate_ai_digest_with_llm()
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
    items = await load_snapshot_or_empty(redis, snapshots.MARKET_INDICATORS)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/anomalies")
async def anomalies() -> ApiResponse[AnomalyOverview]:
    redis = get_container().redis.get_client()
    data = await load_snapshot_or_empty(redis, snapshots.ANOMALIES)
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
