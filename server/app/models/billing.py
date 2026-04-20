"""
计费模型 —— 电池流水与套餐订单

BatteryLedger: 每次电池增减的流水记录（充值/消耗/赠送）
MembershipOrder: 会员套餐购买订单
"""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class BatteryLedger(Base, TimestampMixin):
    """电池流水记录"""
    __tablename__ = "battery_ledger"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # 正数=充入，负数=消耗
    change: Mapped[int] = mapped_column(Integer, nullable=False)
    # 变更后余额（方便追溯）
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")

    user = relationship("User", back_populates="battery_ledger")


class MembershipOrder(Base, TimestampMixin):
    """会员套餐购买订单"""
    __tablename__ = "membership_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    # 套餐标识
    plan_id: Mapped[str] = mapped_column(String(36), nullable=False)
    plan_name: Mapped[str] = mapped_column(String(64), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    battery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # pending / paid / cancelled / refunded
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
