"""
题材掘金 · 事件驱动路由。

5 个接口：
  GET  /event-driven/access-status  访问状态（VIP / 单日解锁 / 算力余额）
  GET  /event-driven/themes         31 个题材列表
  GET  /event-driven/themes/{id}    单个题材完整内容（8 大模块）
  GET  /event-driven/they-say       今日「它们说」AI 共识看板
  POST /event-driven/unlock         单日算力解锁（登录后真实扣减算力）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.container import get_container
from app.core.security import get_optional_current_user_id
from app.modules.page_cache import delete_cached, load_cached, save_cached
from app.modules.event_driven.schemas import (
    AccessStatus,
    TheySayBoard,
    ThemeDetail,
    ThemeListItem,
    UnlockResult,
)
from app.modules.event_driven.service import EventDrivenService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/event-driven", tags=["event-driven"])
service = EventDrivenService(cache_only=True)
_CACHE_NAME = "event-driven:market-snapshot"
_CACHE_TTL_SECONDS = 10 * 60
_CACHE_ADAPTER = TypeAdapter(dict)
_ACCESS_STATUS_ADAPTER = TypeAdapter(AccessStatus)


def _access_status_cache_name(user_id: str | None) -> str:
    return f"event-driven:access-status:{user_id or 'anonymous'}"


async def refresh_event_driven_cache() -> None:
    snapshot = service.refresh_cached_market_snapshot()
    redis = get_container().redis.get_client()
    await save_cached(redis, _CACHE_NAME, snapshot.to_cache_payload(), ttl_seconds=_CACHE_TTL_SECONDS)


async def _ensure_cache_loaded() -> None:
    try:
        redis = get_container().redis.get_client()
        payload = await load_cached(redis, _CACHE_NAME, _CACHE_ADAPTER)
        if payload is not None:
            service.set_cached_market_snapshot_payload(payload)
    except Exception:
        pass


@router.get("/access-status")
async def access_status(
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[AccessStatus]:
    if session:
        try:
            redis = get_container().redis.get_client()
            cached = await load_cached(redis, _access_status_cache_name(user_id), _ACCESS_STATUS_ADAPTER)
            if cached is not None:
                return ApiResponse(data=cached)
        except Exception:
            pass
    data = await service.async_access_status(session, user_id)
    if session:
        try:
            redis = get_container().redis.get_client()
            await save_cached(redis, _access_status_cache_name(user_id), data, ttl_seconds=60)
        except Exception:
            pass
    return ApiResponse(data=data)


@router.get("/themes")
async def list_themes() -> ApiResponse[ListResponse[ThemeListItem]]:
    await _ensure_cache_loaded()
    items = service.list_themes()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/themes/{theme_id}")
async def get_theme(theme_id: str) -> ApiResponse[ThemeDetail]:
    await _ensure_cache_loaded()
    detail = service.get_theme(theme_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"theme '{theme_id}' not found")
    return ApiResponse(data=detail)


@router.get("/they-say")
async def they_say() -> ApiResponse[TheySayBoard]:
    await _ensure_cache_loaded()
    return ApiResponse(data=service.they_say())


@router.post("/unlock")
async def unlock(
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[UnlockResult]:
    data = await service.async_unlock(session, user_id)
    if session:
        try:
            redis = get_container().redis.get_client()
            await delete_cached(redis, _access_status_cache_name(user_id))
        except Exception:
            pass
    return ApiResponse(data=data)
