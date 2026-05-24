from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.security import get_optional_current_user_id
from app.modules.documents.schemas import (
    DocumentComment,
    DocumentCreateCommentRequest,
    DocumentDetail,
    DocumentSummary,
    DocumentType,
)
from app.modules.documents.service import DocumentService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/documents", tags=["documents"])
service = DocumentService()


@router.get("")
async def list_documents(
    doc_type: DocumentType | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1),
    page: int | None = Query(default=None, ge=1),
    page_size: int | None = Query(default=None, ge=1, le=100),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[DocumentSummary]]:
    if not session:
        items, total = service.list_documents(
            doc_type=doc_type,
            limit=limit,
            page=page,
            page_size=page_size,
        )
        return ApiResponse(data=ListResponse(items=items, total=total))
    items, total = await service.async_list_documents(
        session,
        doc_type=doc_type,
        limit=limit,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(data=ListResponse(items=items, total=total))


@router.get("/hot")
async def hot_documents(
    limit: int = 5,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[DocumentSummary]]:
    if not session:
        items = service.hot_documents(limit=limit)
        return ApiResponse(data=ListResponse(items=items, total=len(items)))
    items = await service.async_hot_documents(session, limit=limit)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[DocumentDetail]:
    if not session:
        return ApiResponse(data=service.get_document(document_id))
    return ApiResponse(data=await service.async_get_document(session, document_id))


@router.get("/{document_id}/comments")
async def list_document_comments(
    document_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[DocumentComment]]:
    if not session:
        items = service.list_comments(document_id)
        return ApiResponse(data=ListResponse(items=items, total=len(items)))
    items = await service.async_list_comments(session, document_id)
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
    return ApiResponse(data=await service.async_create_comment(session, document_id, user_id or "anonymous", payload))
