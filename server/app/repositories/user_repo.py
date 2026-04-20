"""
用户 Repository —— User 表的数据访问层

提供：
  - get_by_phone: 按手机号查找用户（登录场景）
  - get_by_id: 按 ID 查找用户（鉴权后获取 profile）
  - create / update / delete: 继承自 BaseRepository
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """用户数据访问"""

    model_class = User

    async def get_by_phone(self, phone: str) -> User | None:
        """按手机号查找用户（用于登录验证）"""
        stmt = select(User).where(User.phone == phone)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_battery(self, user: User, delta: int) -> User:
        """增减电池余额（正数充入，负数消耗），返回更新后的用户"""
        user.battery_balance += delta
        await self.session.flush()
        await self.session.refresh(user)
        return user
