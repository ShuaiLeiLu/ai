"""
ORM 模型注册中心

所有模型必须在此 import，否则 Alembic 无法检测到对应的数据表。
"""
from app.models.base import Base, TimestampMixin
from app.models.billing import BatteryLedger, MembershipOrder
from app.models.community import Comment, Post
from app.models.document import Document
from app.models.ecosystem import KnowledgeBase, McpAuthorization, McpServer, SkillPack
from app.models.researcher import Researcher, ResearcherHire
from app.models.trading import Position, TradingAccount, TradeRecord
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    # 用户
    "User",
    # 研究员
    "Researcher",
    "ResearcherHire",
    # 文档
    "Document",
    # 社区
    "Post",
    "Comment",
    # 交易
    "TradingAccount",
    "Position",
    "TradeRecord",
    # 计费
    "BatteryLedger",
    "MembershipOrder",
    # 生态
    "KnowledgeBase",
    "SkillPack",
    "McpServer",
    "McpAuthorization",
]
