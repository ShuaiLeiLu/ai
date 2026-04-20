"""
资讯路由

所有 API 保持原有契约不变，内部改为通过 run_sync 异步调用。
"""
from __future__ import annotations

from fastapi import APIRouter

from app.integrations.akshare.client import run_sync
from app.modules.news.schemas import NewsDigest, NewsItem, Sentiment
from app.modules.news.service import NewsService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/news", tags=["news"])
service = NewsService()


@router.get("")
async def list_news(
    important_only: bool = False,
    sentiment: Sentiment | None = None,
) -> ApiResponse[ListResponse[NewsItem]]:
    items = await run_sync(service.list_news, important_only=important_only, sentiment=sentiment)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/digest/latest")
async def latest_digest() -> ApiResponse[NewsDigest]:
    data = await run_sync(service.latest_digest)
    return ApiResponse(data=data)
