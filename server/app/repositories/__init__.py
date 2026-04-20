"""
Repository 注册中心

所有业务 Repository 在此统一导出，方便 Service 层按需导入。
"""
from app.repositories.base import BaseRepository
from app.repositories.billing_repo import BatteryLedgerRepository, MembershipOrderRepository
from app.repositories.community_repo import CommentRepository, PostRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.ecosystem_repo import (
    KnowledgeBaseRepository,
    McpAuthorizationRepository,
    McpServerRepository,
    SkillPackRepository,
)
from app.repositories.researcher_repo import ResearcherHireRepository, ResearcherRepository
from app.repositories.trading_repo import PositionRepository, TradingAccountRepository, TradeRecordRepository
from app.repositories.user_repo import UserRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "ResearcherRepository",
    "ResearcherHireRepository",
    "DocumentRepository",
    "PostRepository",
    "CommentRepository",
    "TradingAccountRepository",
    "PositionRepository",
    "TradeRecordRepository",
    "BatteryLedgerRepository",
    "MembershipOrderRepository",
    "KnowledgeBaseRepository",
    "SkillPackRepository",
    "McpServerRepository",
    "McpAuthorizationRepository",
]
