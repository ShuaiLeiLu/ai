from __future__ import annotations

from fastapi import APIRouter

from app.modules.notes.schemas import FolderItem, NoteItem, NoteUpsertRequest
from app.modules.notes.service import NoteService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/notes", tags=["notes"])
service = NoteService()


@router.get("/folders")
async def list_folders() -> ApiResponse[ListResponse[FolderItem]]:
    items = service.list_folders()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("")
async def list_notes(folder_id: str | None = None) -> ApiResponse[ListResponse[NoteItem]]:
    items = service.list_notes(folder_id=folder_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.post("")
async def create_note(payload: NoteUpsertRequest) -> ApiResponse[NoteItem]:
    return ApiResponse(data=service.upsert_note(note_id=None, payload=payload))


@router.put("/{note_id}")
async def update_note(note_id: str, payload: NoteUpsertRequest) -> ApiResponse[NoteItem]:
    return ApiResponse(data=service.upsert_note(note_id=note_id, payload=payload))
