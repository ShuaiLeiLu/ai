"""
研究员 Repository —— Researcher / ResearcherHire 表的数据访问层

提供：
  - 研究员 CRUD + 发布/下架
  - 按 owner_id 查询用户创建的研究员
  - 按 visibility='public' 查询市场公开研究员
  - 雇佣关系管理（hire / dismiss / list_hired）
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.researcher import Researcher, ResearcherHire
from app.repositories.base import BaseRepository


class ResearcherRepository(BaseRepository[Researcher]):
    """研究员数据访问"""

    model_class = Researcher

    async def list_by_owner(self, owner_id: str, *, offset: int = 0, limit: int = 50) -> list[Researcher]:
        """查询某用户创建的所有研究员"""
        return await self.list_all(
            filters=[Researcher.owner_id == owner_id],
            order_by=Researcher.created_at.desc(),
            offset=offset,
            limit=limit,
        )

    async def list_public(self, *, offset: int = 0, limit: int = 50) -> list[Researcher]:
        """查询市场上公开的研究员（visibility = public）"""
        return await self.list_all(
            filters=[Researcher.visibility == "public"],
            order_by=Researcher.hire_count.desc(),
            offset=offset,
            limit=limit,
        )


class ResearcherHireRepository(BaseRepository[ResearcherHire]):
    """雇佣关系数据访问"""

    model_class = ResearcherHire

    async def find_hire(self, user_id: str, researcher_id: str) -> ResearcherHire | None:
        """查找指定用户与研究员之间的雇佣关系"""
        stmt = select(ResearcherHire).where(
            ResearcherHire.user_id == user_id,
            ResearcherHire.researcher_id == researcher_id,
            ResearcherHire.status == "hired",
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_hired_by_user(self, user_id: str) -> list[ResearcherHire]:
        """查询某用户雇佣的所有研究员关系"""
        return await self.list_all(
            filters=[
                ResearcherHire.user_id == user_id,
                ResearcherHire.status == "hired",
            ],
            order_by=ResearcherHire.created_at.desc(),
        )
