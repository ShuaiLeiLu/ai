"""盘前市场快照模型。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class PreopenMarketSnapshot(Base, TimestampMixin):
    """每日盘前/盘后市场结构快照，用于真实多日趋势。"""

    __tablename__ = "preopen_market_snapshots"
    __table_args__ = (
        Index("ix_preopen_market_snapshots_trade_date", "trade_date", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    limit_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    limit_down_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_limit_up_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    highest_consecutive: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    strong_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    break_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seal_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    top_industries: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)


class PreopenAiDigest(Base, TimestampMixin):
    """每日盘前 AI 主线判断输出。

    供次日 YesterdayReviewSkill 读取昨日判断,与今日真实走势对比,
    生成自我反思纳入新一天的 main_thesis。
    """

    __tablename__ = "preopen_ai_digests"
    __table_args__ = (
        Index("ix_preopen_ai_digests_trade_date", "trade_date", unique=True),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    # 综合 skill 完整 markdown
    main_thesis_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # {skill_name: {narrative, structured}}
    skill_outputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # 可证伪信号数组,供次日 review 对照
    falsification_signals: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list,
    )
    # 主线方向:bullish/bearish/mixed/retreat 等
    bias: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SkillRunLog(Base, TimestampMixin):
    """每次 skill 调用的执行日志(评估用)。

    用于评估每个 skill 的:
      - 平均耗时
      - 失败率
      - token 消耗
      - 输出体量
    """

    __tablename__ = "skill_run_logs"
    __table_args__ = (
        Index("ix_skill_run_logs_skill_name_created", "skill_name", "created_at"),
    )

    id: Mapped[str] = mapped_column(primary_key=True)
    skill_name: Mapped[str] = mapped_column(Text, nullable=False)
    chain_kind: Mapped[str] = mapped_column(Text, nullable=False, default="")  # preopen / daily_review
    trade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    researcher_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    narrative_len: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
