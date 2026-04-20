"""
用户模型 —— 账户与会员体系

字段设计：
  - phone: 手机号（唯一标识，用于登录）
  - password_hash: bcrypt 哈希后的密码
  - nickname: 昵称
  - avatar_url: 头像链接（可选）
  - membership_level: 会员等级（普通用户 / VIP1 / VIP2 / VIP3）
  - battery_balance: 电池余额（整数，每次操作增减）
  - is_active: 是否启用
"""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), nullable=False, default="新用户")
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    membership_level: Mapped[str] = mapped_column(String(20), nullable=False, default="普通用户")
    battery_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # 关联
    researchers = relationship("Researcher", back_populates="owner", lazy="selectin")
    battery_ledger = relationship("BatteryLedger", back_populates="user", lazy="selectin")
    posts = relationship("Post", back_populates="author", lazy="selectin")
