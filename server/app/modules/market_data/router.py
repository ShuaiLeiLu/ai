from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.integrations.jin10.client import Jin10McpError
from app.modules.market_data.schemas import (
    CalendarItem,
    CursorPage,
    KlineData,
    NewsDetail,
    QuoteCode,
    QuoteSnapshot,
)
from app.modules.market_data.service import MarketDataService, UnknownQuoteCodeError
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/market-data", tags=["market-data"])
service = MarketDataService()


def _raise_upstream_error(exc: Jin10McpError) -> None:
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(exc),
    ) from exc


@router.get("/quote-codes")
async def quote_codes() -> ApiResponse[ListResponse[QuoteCode]]:
    try:
        items = await service.list_quote_codes()
    except Jin10McpError as exc:
        _raise_upstream_error(exc)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/quotes/{code}")
async def get_quote(code: str) -> ApiResponse[QuoteSnapshot]:
    try:
        return ApiResponse(data=await service.get_quote(code))
    except UnknownQuoteCodeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Jin10McpError as exc:
        _raise_upstream_error(exc)


@router.get("/klines/{code}")
async def get_kline(
    code: str,
    time: int | None = Query(default=None),
    count: int | None = Query(default=None, ge=1, le=100),
) -> ApiResponse[KlineData]:
    try:
        return ApiResponse(data=await service.get_kline(code, time=time, count=count))
    except UnknownQuoteCodeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Jin10McpError as exc:
        _raise_upstream_error(exc)


@router.get("/flash")
async def list_flash(cursor: str | None = None) -> ApiResponse[CursorPage]:
    try:
        return ApiResponse(data=await service.list_flash(cursor=cursor))
    except Jin10McpError as exc:
        _raise_upstream_error(exc)


@router.get("/flash/search")
async def search_flash(keyword: str = Query(min_length=1)) -> ApiResponse[CursorPage]:
    try:
        return ApiResponse(data=await service.search_flash(keyword))
    except Jin10McpError as exc:
        _raise_upstream_error(exc)


@router.get("/news")
async def list_news(cursor: str | None = None) -> ApiResponse[CursorPage]:
    try:
        return ApiResponse(data=await service.list_news(cursor=cursor))
    except Jin10McpError as exc:
        _raise_upstream_error(exc)


@router.get("/news/search")
async def search_news(
    keyword: str = Query(min_length=1),
    cursor: str | None = None,
) -> ApiResponse[CursorPage]:
    try:
        return ApiResponse(data=await service.search_news(keyword, cursor=cursor))
    except Jin10McpError as exc:
        _raise_upstream_error(exc)


@router.get("/news/{news_id}")
async def get_news(news_id: str) -> ApiResponse[NewsDetail]:
    try:
        return ApiResponse(data=await service.get_news(news_id))
    except Jin10McpError as exc:
        _raise_upstream_error(exc)


@router.get("/calendar")
async def calendar() -> ApiResponse[ListResponse[CalendarItem]]:
    try:
        items = await service.list_calendar()
    except Jin10McpError as exc:
        _raise_upstream_error(exc)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))

