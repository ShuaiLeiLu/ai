"""
交易模型 —— 模拟交易账户、持仓、成交记录与交易日志

每个用户的每个研究员关联一个模拟账户，
持仓表记录当前持有股票，成交记录表记录买卖历史，
交易日志表记录带时间戳的富文本日志（包含交易表格和AI分析文本）。
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Index, Integer, String, Text
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
