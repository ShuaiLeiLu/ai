"""
生态系统 Repository —— KnowledgeBase / SkillPack / McpServer 表的数据访问层

提供：
  - 知识库：按 owner_id 查询
  - 技能包：按分类/热门筛选
  - MCP 服务器：按分类/授权状态筛选
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ecosystem import KnowledgeBase, McpAuthorization, McpServer, SkillPack
from app.repositories.base import BaseRepository


class KnowledgeBaseRepository(BaseRepository[KnowledgeBase]):
    """知识库数据访问"""

    model_class = KnowledgeBase

    async def list_by_owner(
        self, owner_id: str, *, offset: int = 0, limit: int = 50
    ) -> list[KnowledgeBase]:
        """查询某用户的知识库列表"""
        return await self.list_all(
            filters=[KnowledgeBase.owner_id == owner_id],
            order_by=KnowledgeBase.created_at.desc(),
            offset=offset,
            limit=limit,
        )


class SkillPackRepository(BaseRepository[SkillPack]):
    """技能包数据访问"""

    model_class = SkillPack

    async def list_hot(self, *, limit: int = 10) -> list[SkillPack]:
        """查询热门技能包"""
        return await self.list_all(
            filters=[SkillPack.is_hot == True],  # noqa: E712
            order_by=SkillPack.install_count.desc(),
            limit=limit,
        )

    async def list_by_category(
        self, category: str, *, offset: int = 0, limit: int = 50
    ) -> list[SkillPack]:
        """按分类查询技能包"""
        return await self.list_all(
            filters=[SkillPack.category == category],
            order_by=SkillPack.install_count.desc(),
            offset=offset,
            limit=limit,
        )


class McpServerRepository(BaseRepository[McpServer]):
    """MCP 服务器数据访问"""

    model_class = McpServer

    async def list_hot(self, *, limit: int = 10) -> list[McpServer]:
        """查询热门 MCP 服务器"""
        return await self.list_all(
            filters=[McpServer.is_hot == True],  # noqa: E712
            order_by=McpServer.install_count.desc(),
            limit=limit,
        )


class McpAuthorizationRepository(BaseRepository[McpAuthorization]):
    """MCP 授权关系数据访问"""

    model_class = McpAuthorization

    async def find_auth(self, user_id: str, mcp_server_id: str) -> McpAuthorization | None:
        """查找用户对某 MCP 服务器的授权关系"""
        stmt = select(McpAuthorization).where(
            McpAuthorization.user_id == user_id,
            McpAuthorization.mcp_server_id == mcp_server_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, user_id: str) -> list[McpAuthorization]:
        """查询某用户的所有 MCP 授权"""
        return await self.list_all(
            filters=[
                McpAuthorization.user_id == user_id,
                McpAuthorization.status == "authorized",
            ],
        )
