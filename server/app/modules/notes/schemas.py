from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import SchemaModel


class FolderItem(SchemaModel):
    folder_id: str
    name: str
    parent_id: str | None = None


class NoteItem(SchemaModel):
    note_id: str
    folder_id: str
    title: str
    content_markdown: str
    updated_at: datetime


class NoteUpsertRequest(SchemaModel):
    folder_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=120)
    content_markdown: str = Field(default="", max_length=30000)
