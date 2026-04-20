"""
社区路由 —— 支持双模式（DB + mock fallback）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.security import get_current_user_id
from app.modules.community.schemas import CommunityCreatePostRequest, CommunityPost, CommunityPostDetail
from app.modules.community.service import CommunityService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/community", tags=["community"])
service = CommunityService()


@router.get("/posts")
async def list_posts(
    q: str | None = Query(default=None),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[CommunityPost]]:
    """帖子列表（DB 查空时 fallback 到 mock）"""
    items = []
    if session:
        items = await service.async_list_posts(session, q=q)
    if not items:
        items = service.list_posts(q=q)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityPostDetail]:
    """帖子详情"""
    if session:
        data = await service.async_get_post(session, post_id)
    else:
        data = service.get_post(post_id)
    return ApiResponse(data=data)


@router.post("/posts")
async def create_post(
    payload: CommunityCreatePostRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityPostDetail]:
    """创建帖子"""
    if session:
        data = await service.async_create_post(session, user_id, payload)
    else:
        data = service.create_post(payload)
    return ApiResponse(data=data)
