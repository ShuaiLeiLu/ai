"""
ORM 模型注册中心

所有模型必须在此 import，否则 Alembic 无法检测到对应的数据表。
"""
from app.models.base import Base, TimestampMixin
from app.models.billing import BatteryLedger, MembershipOrder
from app.models.community import Comment, Post
from app.models.document import Document
from app.models.ecosystem import KnowledgeBase, McpAuthorization, McpServer, SkillPack
from app.models.preopen import PreopenAiDigest, PreopenMarketSnapshot, SkillRunLog
from app.models.researcher import Researcher, ResearcherHire, ResearcherThesisLog
from app.models.task import OrchestrationTask, OrchestrationTaskRun, OrchestrationTaskRunLog
from app.models.trading import (
    DailyReviewReport,
    PendingOrder,
    Position,
    TradeLog,
    TradeRecord,
    TradingAccount,
    TradingAccountMinuteSnapshot,
    TradingAccountSnapshot,
)
from app.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    # 用户
    "User",
    # 研究员
    "Researcher",
    "ResearcherHire",
    "ResearcherThesisLog",
    # 任务编排
    "OrchestrationTask",
    "OrchestrationTaskRun",
    "OrchestrationTaskRunLog",
    # 文档
    "Document",
    # 社区
    "Post",
    "Comment",
    # 交易
    "TradingAccount",
    "TradingAccountSnapshot",
    "TradingAccountMinuteSnapshot",
    "PendingOrder",
    "Position",
    "TradeRecord",
    "TradeLog",
    "DailyReviewReport",
    # 盘前
    "PreopenMarketSnapshot",
    "PreopenAiDigest",
    "SkillRunLog",
    # 计费
    "BatteryLedger",
    "MembershipOrder",
    # 生态
    "KnowledgeBase",
    "SkillPack",
    "McpServer",
    "McpAuthorization",
]
