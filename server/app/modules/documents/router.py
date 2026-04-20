from __future__ import annotations

from fastapi import APIRouter, Query

from app.modules.documents.schemas import DocumentDetail, DocumentSummary, DocumentType
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
) -> ApiResponse[ListResponse[DocumentSummary]]:
    items, total = service.list_documents(
        doc_type=doc_type,
        limit=limit,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(data=ListResponse(items=items, total=total))


@router.get("/hot")
async def hot_documents(limit: int = 5) -> ApiResponse[ListResponse[DocumentSummary]]:
    items = service.hot_documents(limit=limit)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/{document_id}")
async def get_document(document_id: str) -> ApiResponse[DocumentDetail]:
    return ApiResponse(data=service.get_document(document_id))
