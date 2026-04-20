"""
资讯分析路由

所有 API 保持原有契约不变，内部改为通过 run_sync 异步调用 AKShare 数据源。
AKShare 是同步阻塞调用，通过线程池避免阻塞 asyncio 事件循环。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.integrations.akshare.client import run_sync
from app.modules.news_analysis.schemas import (
    HotNewsRankItem,
    HotStockTag,
    NewsAiPanel,
    NewsAnalysisItem,
    NewsFeedCategory,
    StockNewsSummary,
)
from app.modules.news_analysis.service import NewsAnalysisService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/news-analysis", tags=["news-analysis"])
service = NewsAnalysisService()


@router.get("/feed")
async def feed(
    category: NewsFeedCategory = "all",
    important_only: bool = False,
    stock_code: str | None = None,
) -> ApiResponse[ListResponse[NewsAnalysisItem]]:
    items = await run_sync(
        service.list_feed, category=category, important_only=important_only, stock_code=stock_code
    )
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/ai-panels")
async def ai_panels() -> ApiResponse[ListResponse[NewsAiPanel]]:
    """AI 智能分析面板 —— 调用 Gemini 生成 AI 解读，失败时自动降级"""
    items = await service.generate_ai_panels_with_llm()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/hot-stocks")
async def hot_stocks() -> ApiResponse[ListResponse[HotStockTag]]:
    items = await run_sync(service.list_hot_stocks)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/hot-news")
async def hot_news() -> ApiResponse[ListResponse[HotNewsRankItem]]:
    items = await run_sync(service.list_hot_news)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/by-stock/{stock_code}/summary")
async def by_stock_summary(stock_code: str) -> ApiResponse[StockNewsSummary]:
    data = await run_sync(service.get_stock_summary, stock_code=stock_code)
    return ApiResponse(data=data)
