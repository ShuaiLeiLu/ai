"""
生态系统领域服务

双模式运行：
  1. 数据库模式（async）：通过各 Repository 操作 PostgreSQL
  2. 内存 mock 模式（sync）：数据库未就绪时的降级方案
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ecosystem.schemas import KnowledgeBaseItem, McpServerItem, SkillItem
from app.repositories.ecosystem_repo import KnowledgeBaseRepository, McpServerRepository, SkillPackRepository


class EcosystemService:
    """生态系统服务 —— 同时支持数据库和内存 mock 两种模式。"""

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
        self._knowledge_bases = [
            KnowledgeBaseItem(kb_id="kb_1", name="A股公告库", document_count=1284, updated_at=now - timedelta(hours=1)),
            KnowledgeBaseItem(kb_id="kb_2", name="行业研报库", document_count=762, updated_at=now - timedelta(hours=3)),
        ]
        self._skills = [
            SkillItem(skill_id="sk_news", name="资讯快读", description="自动摘要并提取交易线索", installed=True),
            SkillItem(skill_id="sk_event", name="事件跟踪", description="监控事件演化并触发任务", installed=False),
        ]
        self._mcp_servers = [
            McpServerItem(server_id="mcp_1", name="行情数据MCP", category="market-data", connected=True),
            McpServerItem(server_id="mcp_2", name="公告检索MCP", category="search", connected=False),
        ]

    def list_knowledge_bases(self) -> list[KnowledgeBaseItem]:
        return self._knowledge_bases

    def list_skills(self, installed: bool | None = None) -> list[SkillItem]:
        if installed is None:
            return self._skills
        return [skill for skill in self._skills if skill.installed is installed]

    def list_mcp_servers(self) -> list[McpServerItem]:
        return self._mcp_servers

    # ──────────── 数据库模式（async） ────────────

    async def async_list_knowledge_bases(
        self, session: AsyncSession, owner_id: str
    ) -> list[KnowledgeBaseItem]:
        """从数据库查询知识库列表"""
        repo = KnowledgeBaseRepository(session)
        items = await repo.list_by_owner(owner_id)
        return [
            KnowledgeBaseItem(
                kb_id=kb.id,
                name=kb.name,
                document_count=kb.doc_count,
                updated_at=kb.updated_at,
            )
            for kb in items
        ]

    async def async_list_skills(self, session: AsyncSession) -> list[SkillItem]:
        """从数据库查询技能包列表"""
        repo = SkillPackRepository(session)
        items = await repo.list_all(limit=100)
        return [
            SkillItem(
                skill_id=sp.id,
                name=sp.name,
                description=sp.description,
                installed=False,  # 需要用户绑定关系表，后续完善
            )
            for sp in items
        ]

    async def async_list_mcp_servers(self, session: AsyncSession) -> list[McpServerItem]:
        """从数据库查询 MCP 服务器列表"""
        repo = McpServerRepository(session)
        items = await repo.list_all(limit=100)
        return [
            McpServerItem(
                server_id=mcp.id,
                name=mcp.name,
                category=mcp.category,
                connected=False,  # 需要用户授权关系表，后续完善
            )
            for mcp in items
        ]
