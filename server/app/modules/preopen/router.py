"""
盘前速览路由

所有 API 保持原有契约不变，内部改为通过 run_sync 异步调用 AKShare 数据源。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.integrations.akshare.client import run_sync
from app.modules.preopen.schemas import (
    AiDigest,
    AnomalyOverview,
    HotNewsItem,
    IndustryBoardItem,
    LimitUpLadderItem,
    MarketIndicator,
    StockRankItem,
    TrendOverview,
)
from app.modules.preopen.service import PreopenService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/preopen", tags=["preopen"])
service = PreopenService()


@router.get("/hot-news")
async def hot_news() -> ApiResponse[ListResponse[HotNewsItem]]:
    items = await run_sync(service.list_hot_news)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/ai-digest")
async def ai_digest() -> ApiResponse[AiDigest]:
    """盘前 AI 解读 —— 调用 Gemini 生成专业分析，失败时自动降级"""
    data = await service.generate_ai_digest_with_llm()
    return ApiResponse(data=data)


@router.get("/market-indicators")
async def market_indicators() -> ApiResponse[ListResponse[MarketIndicator]]:
    items = await run_sync(service.list_market_indicators)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/anomalies")
async def anomalies() -> ApiResponse[AnomalyOverview]:
    data = await run_sync(service.get_anomalies)
    return ApiResponse(data=data)


@router.get("/trends")
async def trends() -> ApiResponse[TrendOverview]:
    data = await run_sync(service.get_trends)
    return ApiResponse(data=data)


@router.get("/limit-up-ladder")
async def limit_up_ladder() -> ApiResponse[ListResponse[LimitUpLadderItem]]:
    items = await run_sync(service.list_limit_up_ladder)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/industry-boards")
async def industry_boards() -> ApiResponse[ListResponse[IndustryBoardItem]]:
    items = await run_sync(service.list_industry_boards)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/stock-rank")
async def stock_rank(direction: str = "up") -> ApiResponse[ListResponse[StockRankItem]]:
    items = await run_sync(service.list_stock_rank, direction=direction)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
