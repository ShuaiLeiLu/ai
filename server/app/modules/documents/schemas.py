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
    is_vip_only: bool = False
    can_view_full: bool = True
    vip_message: str | None = None


class DocumentDetail(DocumentSummary):
    content_markdown: str
    tags: list[str]
    workflow_nodes: list["DocumentWorkflowNode"] = []


class DocumentWorkflowNode(SchemaModel):
    label: str
    caption: str
    state: Literal["done", "active", "pending"]


class DocumentComment(SchemaModel):
    comment_id: str
    author: str
    author_type: str = "user"
    content: str
    likes: int = 0
    created_at: datetime
    reply_to_id: str | None = None
    reply_to_author: str | None = None


class DocumentCreateCommentRequest(SchemaModel):
    content: str
    reply_to_id: str | None = None
