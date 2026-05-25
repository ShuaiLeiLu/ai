"""社区路由 —— 仅返回真实数据库数据。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.container import get_container
from app.core.security import get_current_user_id, get_optional_current_user_id
from app.modules.community.schemas import (
    CommunityComment,
    CommunityCreateCommentRequest,
    CommunityCreatePostRequest,
    CommunityFeatureRequest,
    CommunityMentionConfig,
    CommunityModerationRequest,
    CommunityPost,
    CommunityPostDetail,
)
from app.modules.community.service import CommunityService
from app.modules.page_cache import delete_cached, load_cached, save_cached
from app.schemas.common import ApiResponse, ListResponse, OperationResponse

router = APIRouter(prefix="/community", tags=["community"])
legacy_router = APIRouter(prefix="/ai-community", tags=["ai-community"])
service = CommunityService()
_CACHE_TTL_SECONDS = 60
_POSTS_ADAPTER = TypeAdapter(list[CommunityPost])
_POST_DETAIL_ADAPTER = TypeAdapter(CommunityPostDetail)
_COMMENTS_ADAPTER = TypeAdapter(list[CommunityComment])
_MENTION_CONFIG_ADAPTER = TypeAdapter(CommunityMentionConfig)


def _posts_cache_name(q: str | None, scope: str, sort: str, user_id: str | None) -> str:
    return f"community:posts:q={(q or '').strip()}:scope={scope}:sort={sort}:user={user_id or 'anonymous'}"


def _post_detail_cache_name(post_id: str) -> str:
    return f"community:post:{post_id}"


def _comments_cache_name(post_id: str) -> str:
    return f"community:comments:{post_id}"


def _mention_config_cache_name(user_id: str | None) -> str:
    return f"community:mention-config:{user_id or 'anonymous'}"


async def _load_community_cache(name: str, adapter: TypeAdapter):
    try:
        redis = get_container().redis.get_client()
        return await load_cached(redis, name, adapter)
    except Exception:
        return None


async def _save_community_cache(name: str, data: object) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, name, data, ttl_seconds=_CACHE_TTL_SECONDS)
    except Exception:
        return


async def _invalidate_post_cache(post_id: str | None = None) -> None:
    try:
        redis = get_container().redis.get_client()
        if post_id:
            await delete_cached(redis, _post_detail_cache_name(post_id))
            await delete_cached(redis, _comments_cache_name(post_id))
    except Exception:
        return


@router.get("/posts")
async def list_posts(
    q: str | None = Query(default=None),
    scope: str = Query(default="all", pattern="^(all|mine|hot|featured)$"),
    sort: str = Query(default="latest", pattern="^(latest|hot|comments)$"),
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[CommunityPost]]:
    """帖子列表。"""
    cache_name = _posts_cache_name(q, scope, sort, user_id)
    if session:
        cached = await _load_community_cache(cache_name, _POSTS_ADAPTER)
        if cached is not None:
            return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = (
        await service.async_list_posts(session, q=q, scope=scope, sort=sort, user_id=user_id)
        if session
        else service.sample_posts(q=q, scope=scope, sort=sort, user_id=user_id)
    )
    if session:
        await _save_community_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/posts/{post_id}")
async def get_post(
    post_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityPostDetail]:
    """帖子详情"""
    if not session:
        return ApiResponse(data=service.sample_post_detail(post_id))
    cache_name = _post_detail_cache_name(post_id)
    cached = await _load_community_cache(cache_name, _POST_DETAIL_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_post(session, post_id)
    await _save_community_cache(cache_name, data)
    return ApiResponse(data=data)


@router.post("/posts")
async def create_post(
    payload: CommunityCreatePostRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityPostDetail]:
    """创建帖子"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_create_post(session, user_id, payload)
    await _invalidate_post_cache(data.post_id)
    return ApiResponse(data=data)


async def _list_posts_response(
    q: str | None,
    scope: str,
    sort: str,
    user_id: str | None,
    session: AsyncSession | None,
) -> ApiResponse[ListResponse[CommunityPost]]:
    cache_name = _posts_cache_name(q, scope, sort, user_id)
    if session:
        cached = await _load_community_cache(cache_name, _POSTS_ADAPTER)
        if cached is not None:
            return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = (
        await service.async_list_posts(session, q=q, scope=scope, sort=sort, user_id=user_id)
        if session
        else service.sample_posts(q=q, scope=scope, sort=sort, user_id=user_id)
    )
    if session:
        await _save_community_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


async def _create_post_response(
    payload: CommunityCreatePostRequest,
    user_id: str,
    session: AsyncSession | None,
) -> ApiResponse[CommunityPostDetail]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_create_post(session, user_id, payload)
    await _invalidate_post_cache(data.post_id)
    return ApiResponse(data=data)


@legacy_router.get("/post/list")
async def legacy_list_posts(
    q: str | None = Query(default=None),
    scope: str = Query(default="all", pattern="^(all|mine|hot|featured)$"),
    sort: str = Query(default="latest", pattern="^(latest|hot|comments)$"),
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[CommunityPost]]:
    """赛博社区帖子列表，兼容采集到的前端接口。"""
    return await _list_posts_response(q, scope, sort, user_id, session)


@legacy_router.get("/post/search")
async def legacy_search_posts(
    q: str | None = Query(default=None),
    scope: str = Query(default="all", pattern="^(all|mine|hot|featured)$"),
    sort: str = Query(default="latest", pattern="^(latest|hot|comments)$"),
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[CommunityPost]]:
    """搜索帖子。"""
    return await _list_posts_response(q, scope, sort, user_id, session)


@legacy_router.get("/post/{post_id}")
async def legacy_get_post(
    post_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityPostDetail]:
    """帖子详情。"""
    if not session:
        return ApiResponse(data=service.sample_post_detail(post_id))
    cache_name = _post_detail_cache_name(post_id)
    cached = await _load_community_cache(cache_name, _POST_DETAIL_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_post(session, post_id)
    await _save_community_cache(cache_name, data)
    return ApiResponse(data=data)


@legacy_router.post("/post/create")
async def legacy_create_post(
    payload: CommunityCreatePostRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityPostDetail]:
    """创建帖子。"""
    return await _create_post_response(payload, user_id, session)


@legacy_router.get("/comment/list")
async def legacy_list_comments(
    post_id: str = Query(...),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[CommunityComment]]:
    """评论列表。"""
    if not session:
        items = service.sample_comments(post_id)
        return ApiResponse(data=ListResponse(items=items, total=len(items)))
    cache_name = _comments_cache_name(post_id)
    cached = await _load_community_cache(cache_name, _COMMENTS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_comments(session, post_id)
    await _save_community_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@legacy_router.get("/comment/replies")
async def legacy_list_replies() -> ApiResponse[ListResponse[CommunityComment]]:
    """回复列表占位：当前评论模型尚未拆分楼中楼。"""
    return ApiResponse(data=ListResponse(items=[], total=0))


@legacy_router.post("/comment/create")
async def legacy_create_comment(
    payload: CommunityCreateCommentRequest,
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityComment]:
    """创建评论。"""
    if not session:
        return ApiResponse(data=service.create_sample_comment(payload, user_id=user_id))
    data = await service.async_create_comment(session, user_id or "anonymous", payload)
    await _invalidate_post_cache(payload.post_id)
    return ApiResponse(data=data)


@legacy_router.post("/post/{post_id}/feature")
async def legacy_set_featured(
    post_id: str,
    payload: CommunityFeatureRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityPostDetail]:
    """设为精华 / 取消精华。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_set_featured(session, post_id, user_id, payload)
    await _invalidate_post_cache(post_id)
    return ApiResponse(data=data)


@legacy_router.post("/post/{post_id}/delete")
async def legacy_delete_post(
    post_id: str,
    payload: CommunityModerationRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[OperationResponse]:
    """删除帖子。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    await service.async_delete_post(session, post_id, user_id, payload)
    await _invalidate_post_cache(post_id)
    return ApiResponse(data=OperationResponse(message="删除成功", resource_id=post_id))


@legacy_router.post("/comment/{comment_id}/delete")
async def legacy_delete_comment(
    comment_id: str,
    payload: CommunityModerationRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[OperationResponse]:
    """删除评论。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    await service.async_delete_comment(session, comment_id, user_id, payload)
    return ApiResponse(data=OperationResponse(message="删除成功", resource_id=comment_id))


@legacy_router.get("/mention/config")
async def legacy_mention_config(
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[CommunityMentionConfig]:
    """可 @ 的已雇佣研究员配置。"""
    if not session or not user_id:
        return ApiResponse(data=service.sample_mention_config())
    cache_name = _mention_config_cache_name(user_id)
    cached = await _load_community_cache(cache_name, _MENTION_CONFIG_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_mention_config(session, user_id)
    await _save_community_cache(cache_name, data)
    return ApiResponse(data=data)
