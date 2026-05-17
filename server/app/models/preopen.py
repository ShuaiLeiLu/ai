"""盘前市场快照模型。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Index, Integer
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
