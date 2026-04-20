"""
生态系统模型 —— 知识库、技能包、MCP 服务

对应赛博实验室中的三大市场：
  - KnowledgeBase: 用户创建的知识库
  - SkillPack: 技能包（可订阅/购买）
  - McpServer: MCP 服务器（第三方工具集成）
"""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class KnowledgeBase(Base, TimestampMixin):
    """知识库"""
    __tablename__ = "knowledge_bases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    doc_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 状态：active / archived
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class SkillPack(Base, TimestampMixin):
    """技能包"""
    __tablename__ = "skill_packs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="通用")
    # 标签列表（JSON 数组）
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # 热门标记
    is_hot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    install_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class McpServer(Base, TimestampMixin):
    """MCP 服务器"""
    __tablename__ = "mcp_servers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="通用")
    # 连接端点
    endpoint_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 标签列表（JSON 数组）
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    is_hot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    install_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class McpAuthorization(Base, TimestampMixin):
    """用户对 MCP 服务器的授权关系"""
    __tablename__ = "mcp_authorizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    mcp_server_id: Mapped[str] = mapped_column(String(36), ForeignKey("mcp_servers.id"), nullable=False, index=True)
    # authorized / revoked
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="authorized")
