from __future__ import annotations

from datetime import datetime

from app.schemas.common import SchemaModel


class KnowledgeBaseItem(SchemaModel):
    kb_id: str
    name: str
    document_count: int
    updated_at: datetime


class SkillItem(SchemaModel):
    skill_id: str
    name: str
    description: str
    installed: bool


class McpServerItem(SchemaModel):
    server_id: str
    name: str
    category: str
    connected: bool
