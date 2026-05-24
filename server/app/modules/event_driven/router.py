"""
题材掘金 · 事件驱动路由。

5 个接口：
  GET  /event-driven/access-status  访问状态（VIP / 单日解锁 / 算力余额）
  GET  /event-driven/themes         31 个题材列表
  GET  /event-driven/themes/{id}    单个题材完整内容（8 大模块）
  GET  /event-driven/they-say       今日「它们说」AI 共识看板
  POST /event-driven/unlock         单日算力解锁（登录后真实扣减电池）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.security import get_optional_current_user_id
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
service = EventDrivenService()


@router.get("/access-status")
async def access_status(
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[AccessStatus]:
    return ApiResponse(data=await service.async_access_status(session, user_id))


@router.get("/themes")
def list_themes() -> ApiResponse[ListResponse[ThemeListItem]]:
    items = service.list_themes()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/themes/{theme_id}")
def get_theme(theme_id: str) -> ApiResponse[ThemeDetail]:
    detail = service.get_theme(theme_id)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"theme '{theme_id}' not found")
    return ApiResponse(data=detail)


@router.get("/they-say")
def they_say() -> ApiResponse[TheySayBoard]:
    return ApiResponse(data=service.they_say())


@router.post("/unlock")
async def unlock(
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[UnlockResult]:
    return ApiResponse(data=await service.async_unlock(session, user_id))
