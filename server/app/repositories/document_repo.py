"""
文档 Repository —— Document 表的数据访问层

提供：
  - 按研究员查询文档列表
  - 热门文档排序（24h 内按 view_count 降序）
  - 按作者查询文档
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    """文档数据访问"""

    model_class = Document

    async def list_by_researcher(
        self, researcher_id: str, *, offset: int = 0, limit: int = 20
    ) -> list[Document]:
        """查询某研究员产出的文档"""
        return await self.list_all(
            filters=[Document.researcher_id == researcher_id],
            order_by=Document.created_at.desc(),
            offset=offset,
            limit=limit,
        )

    async def list_hot(self, *, hours: int = 24, limit: int = 10) -> list[Document]:
        """查询最近 N 小时内的热门文档（按浏览量降序）"""
        since = datetime.now(tz=UTC) - timedelta(hours=hours)
        return await self.list_all(
            filters=[Document.created_at >= since],
            order_by=Document.view_count.desc(),
            limit=limit,
        )

    async def list_by_author(
        self, author_id: str, *, offset: int = 0, limit: int = 20
    ) -> list[Document]:
        """查询某用户创作的文档"""
        return await self.list_all(
            filters=[Document.author_id == author_id],
            order_by=Document.created_at.desc(),
            offset=offset,
            limit=limit,
        )
