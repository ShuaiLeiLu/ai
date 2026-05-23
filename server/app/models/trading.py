"""
交易模型 —— 模拟交易账户、持仓、成交记录与交易日志

每个用户的每个研究员关联一个模拟账户，
持仓表记录当前持有股票，成交记录表记录买卖历史，
交易日志表记录带时间戳的富文本日志（包含交易表格和AI分析文本）。
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class TradingAccount(Base, TimestampMixin):
    """模拟交易账户"""
    __tablename__ = "trading_accounts"
    __table_args__ = (
        Index("ix_trading_accounts_user_researcher", "user_id", "researcher_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    researcher_id: Mapped[str] = mapped_column(String(36), ForeignKey("researchers.id"), nullable=False, index=True)
    # 资金
    total_asset: Mapped[float] = mapped_column(Float, nullable=False, default=1000000.0)
    available_cash: Mapped[float] = mapped_column(Float, nullable=False, default=1000000.0)
    holding_value: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    positions = relationship("Position", back_populates="account", lazy="selectin")
    trades = relationship("TradeRecord", back_populates="account", lazy="selectin")


class Position(Base, TimestampMixin):
    """持仓记录"""
    __tablename__ = "positions"
    __table_args__ = (
        Index("ix_positions_account_symbol", "account_id", "symbol"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_accounts.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    current_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    account = relationship("TradingAccount", back_populates="positions")


class TradeRecord(Base, TimestampMixin):
    """成交记录"""
    __tablename__ = "trade_records"
    __table_args__ = (
        Index("ix_trade_records_account_created_at", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_accounts.id"), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # buy / sell
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    # 手续费
    commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    account = relationship("TradingAccount", back_populates="trades")


class TradeLog(Base, TimestampMixin):
    """交易日志条目

    log_type:
      - trade   : 交易表格（关联 trade_record_ids，前端渲染成表格）
      - analysis: AI 分析文本（Markdown 格式）
    """
    __tablename__ = "trade_logs"
    __table_args__ = (
        Index("ix_trade_logs_account_created_at", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_accounts.id"), nullable=False, index=True)
    # trade / analysis
    log_type: Mapped[str] = mapped_column(String(20), nullable=False, default="trade")
    # JSON: 关联的 trade_record id 列表（log_type=trade 时）
    trade_record_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    # 富文本内容（Markdown，log_type=analysis 时）
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 标题（可选，如 "当前操作情况总结"）
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    account = relationship("TradingAccount")


class TradingAccountSnapshot(Base, TimestampMixin):
    """每日账户快照，用于真实历史收益曲线和投资日历。"""
    __tablename__ = "trading_account_snapshots"
    __table_args__ = (
        Index("ix_trading_account_snapshots_account_date", "account_id", "trade_date", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(String(36), ForeignKey("trading_accounts.id"), nullable=False, index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_asset: Mapped[float] = mapped_column(Float, nullable=False)
    available_cash: Mapped[float] = mapped_column(Float, nullable=False)
    holding_value: Mapped[float] = mapped_column(Float, nullable=False)
    daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    account = relationship("TradingAccount")


class PendingOrder(Base, TimestampMixin):
    """挂单(限价单未成交时落库,盘中撮合循环扫描)。

    生命周期:
      ACTIVE      -> 等待撮合
      FILLED      -> 已成交(对应 trade_records 中的 trade_id)
      CANCELLED   -> 用户主动取消 / 资金或持仓不足
      EXPIRED     -> 当日 15:00 自动过期
    """

    __tablename__ = "pending_orders"
    __table_args__ = (
        Index("ix_pending_orders_account_status", "account_id", "status"),
        Index("ix_pending_orders_symbol_status", "symbol", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trading_accounts.id"), nullable=False, index=True,
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[float] = mapped_column(Float, nullable=False)
    # ACTIVE / FILLED / CANCELLED / EXPIRED
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    # 当日 15:00 自动过期
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    # 成交时回填
    filled_trade_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    filled_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    filled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class TradingAccountMinuteSnapshot(Base, TimestampMixin):
    """模拟账户分钟级权益快照。

    交易时段(09:30-11:30, 13:00-15:00)每分钟由调度器写入一条,
    用于盘中实时收益曲线 + 分钟/小时/日多粒度聚合。
    保留约 30 天,过期由清理任务删除。
    """

    __tablename__ = "trading_account_minute_snapshots"
    __table_args__ = (
        Index(
            "ix_trading_account_minute_snapshots_account_time",
            "account_id", "snapshot_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("trading_accounts.id"), nullable=False, index=True,
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    total_asset: Mapped[float] = mapped_column(Float, nullable=False)
    available_cash: Mapped[float] = mapped_column(Float, nullable=False)
    holding_value: Mapped[float] = mapped_column(Float, nullable=False)
    daily_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class DailyReviewReport(Base, TimestampMixin):
    """盘后教练复盘报告。

    每个研究员每个交易日一条。embedding 列供 pattern_match skill 做 RAG。
    """

    __tablename__ = "daily_review_reports"
    __table_args__ = (
        Index(
            "ix_daily_review_reports_researcher_date",
            "researcher_id", "trade_date", unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    researcher_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("researchers.id"), nullable=False, index=True,
    )
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    coach_report_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skill_outputs: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # 当日 alpha 指标
    alpha_vs_index: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    alpha_vs_sector: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_pnl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # embedding 数组(text-embedding-3-small 1536 维),JSONB 落库
    # 注:服务器未安装 pgvector,RAG 检索由 Python 端做余弦相似度
    embedding: Mapped[list[float] | None] = mapped_column(
        JSONB, nullable=True,
    )
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
