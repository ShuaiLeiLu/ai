from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.common import SchemaModel

DocumentType = Literal["market", "stock", "industry", "topic"]


class DocumentSummary(SchemaModel):
    document_id: str
    title: str
    researcher_name: str
    document_type: DocumentType
    symbol: str | None = None
    view_count: int
    like_count: int
    created_at: datetime


class DocumentDetail(DocumentSummary):
    content_markdown: str
    tags: list[str]
