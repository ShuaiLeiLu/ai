from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.container import get_container
from app.core.security import get_optional_current_user_id
from app.modules.documents.schemas import (
    DocumentComment,
    DocumentCreateCommentRequest,
    DocumentDetail,
    DocumentSummary,
    DocumentType,
)
from app.modules.documents.service import DocumentService
from app.modules.page_cache import delete_cached, load_cached, save_cached
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/documents", tags=["documents"])
service = DocumentService()
_CACHE_TTL_SECONDS = 120
_DOCUMENT_LIST_ADAPTER = TypeAdapter(list[DocumentSummary])
_DOCUMENT_SUMMARY_ADAPTER = TypeAdapter(list[DocumentSummary])
_DOCUMENT_DETAIL_ADAPTER = TypeAdapter(DocumentDetail)
_DOCUMENT_COMMENTS_ADAPTER = TypeAdapter(list[DocumentComment])


def _documents_list_cache_name(
    doc_type: DocumentType | None,
    limit: int | None,
    page: int | None,
    page_size: int | None,
) -> str:
    return f"documents:list:{doc_type or 'all'}:{limit or 'none'}:{page or 'none'}:{page_size or 'none'}"


def _documents_hot_cache_name(limit: int) -> str:
    return f"documents:hot:{limit}"


def _document_detail_cache_name(document_id: str) -> str:
    return f"documents:detail:{document_id}"


def _document_comments_cache_name(document_id: str) -> str:
    return f"documents:comments:{document_id}"


async def _load_document_cache(name: str, adapter: TypeAdapter):
    try:
        redis = get_container().redis.get_client()
        return await load_cached(redis, name, adapter)
    except Exception:
        return None


async def _save_document_cache(name: str, data: object) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, name, data, ttl_seconds=_CACHE_TTL_SECONDS)
    except Exception:
        return


async def _invalidate_document_cache(document_id: str | None = None) -> None:
    try:
        redis = get_container().redis.get_client()
        if document_id:
            await delete_cached(redis, _document_detail_cache_name(document_id))
            await delete_cached(redis, _document_comments_cache_name(document_id))
    except Exception:
        return


@router.get("")
async def list_documents(
    doc_type: DocumentType | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[DocumentSummary]]:
    cache_name = _documents_list_cache_name(doc_type, limit, page, page_size)
    if not session:
        items, total = service.list_documents(
            doc_type=doc_type,
            limit=limit,
            page=page,
            page_size=page_size,
        )
        return ApiResponse(data=ListResponse(items=items, total=total))
    cached = await _load_document_cache(cache_name, _DOCUMENT_LIST_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items, total = await service.async_list_documents(
        session,
        doc_type=doc_type,
        limit=limit,
        page=page,
        page_size=page_size,
    )
    await _save_document_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=total))


@router.get("/hot")
async def hot_documents(
    limit: int = 5,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[DocumentSummary]]:
    cache_name = _documents_hot_cache_name(limit)
    if not session:
        items = service.hot_documents(limit=limit)
        return ApiResponse(data=ListResponse(items=items, total=len(items)))
    cached = await _load_document_cache(cache_name, _DOCUMENT_SUMMARY_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_hot_documents(session, limit=limit)
    await _save_document_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[DocumentDetail]:
    if not session:
        return ApiResponse(data=service.get_document(document_id))
    cache_name = _document_detail_cache_name(document_id)
    cached = await _load_document_cache(cache_name, _DOCUMENT_DETAIL_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_document(session, document_id)
    await _save_document_cache(cache_name, data)
    return ApiResponse(data=data)


@router.get("/{document_id}/comments")
async def list_document_comments(
    document_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[DocumentComment]]:
    if not session:
        items = service.list_comments(document_id)
        return ApiResponse(data=ListResponse(items=items, total=len(items)))
    cache_name = _document_comments_cache_name(document_id)
    cached = await _load_document_cache(cache_name, _DOCUMENT_COMMENTS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_comments(session, document_id)
    await _save_document_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.post("/{document_id}/comments")
async def create_document_comment(
    document_id: str,
    payload: DocumentCreateCommentRequest,
    user_id: str | None = Depends(get_optional_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[DocumentComment]:
    if not session:
        return ApiResponse(data=service.create_comment(document_id, payload, user_id=user_id))
    data = await service.async_create_comment(session, document_id, user_id or "anonymous", payload)
    await _invalidate_document_cache(document_id)
    return ApiResponse(data=data)
