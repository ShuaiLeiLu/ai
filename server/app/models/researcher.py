"""
研究员模型 —— AI 研究员核心实体

包含：
  - Researcher: 研究员主表（名称/描述/提示词/技能配置/发布状态等）
  - ResearcherHire: 雇佣关系表（用户 ↔ 研究员多对多）

发布状态流转：
  draft → published（visibility 变 public，生成版本号）
  published → unpublished（visibility 变 private，保留版本号）
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Researcher(Base, TimestampMixin):
    """研究员主表"""
    __tablename__ = "researchers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False, default="自定义研究员")
    style: Mapped[str] = mapped_column(String(64), nullable=False, default="均衡")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 状态：active / idle / dismissed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="idle")
    # 可见性：draft / private / public
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # 发布状态：draft / published / unpublished
    publish_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    published_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="v0")

    # 等级与收益指标
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="LV.1")
    today_pnl: Mapped[float] = mapped_column(default=0.0)
    win_rate_30d: Mapped[float] = mapped_column(default=0.0)

    # JSON 数组字段（技能/知识库/MCP/标签/自驱任务）
    skills: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    knowledge_bases: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    mcp_servers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    self_drive_tasks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    # 策略配置（JSONB）—— 每个研究员的专属交易策略参数
    # 结构示例：{
    #   "strategy_type": "smallcap_rotation",
    #   "stock_count": 10,
    #   "factors": [...],
    #   "filters": {...},
    #   "risk_control": {...},
    #   "schedule": {...},
    #   "cost": {...}
    # }
    strategy_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=None)

    # 系统内定研究员标志 —— True 表示对所有用户可见，无需雇佣
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # 雇佣数
    hire_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # 关联
    owner = relationship("User", back_populates="researchers")
    hires = relationship("ResearcherHire", back_populates="researcher", lazy="selectin")
    documents = relationship("Document", back_populates="researcher", lazy="selectin")


class ResearcherHire(Base, TimestampMixin):
    """雇佣关系表 —— 用户雇佣研究员的多对多中间表"""
    __tablename__ = "researcher_hires"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    researcher_id: Mapped[str] = mapped_column(String(36), ForeignKey("researchers.id"), nullable=False, index=True)
    # hired / dismissed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="hired")

    researcher = relationship("Researcher", back_populates="hires")


class ResearcherThesisLog(Base, TimestampMixin):
    """研究员每日判断累积评分卡。

    main_thesis skill 生成主线判断后写入一条;
    T+1 凌晨异步任务对照实际市场,回填 actual_result 和 correctness。
    """

    __tablename__ = "researcher_thesis_logs"
    __table_args__ = (
        Index(
            "ix_researcher_thesis_logs_researcher_date",
            "researcher_id", "trade_date",
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("researchers.id"), nullable=False, index=True,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)

    direction_call: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    key_drivers: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    falsification_signals: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
    )
    # 由异步评估任务回填:T+1 / T+5 实际表现
    actual_result: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # correct / partial / wrong / pending
    correctness: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
    )
