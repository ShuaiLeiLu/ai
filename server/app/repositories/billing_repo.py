"""
计费 Repository —— BatteryLedger / MembershipOrder 表的数据访问层

提供：
  - 电池流水查询（按时间降序）
  - 套餐订单查询
"""
from __future__ import annotations

from app.models.billing import BatteryLedger, MembershipOrder
from app.repositories.base import BaseRepository


class BatteryLedgerRepository(BaseRepository[BatteryLedger]):
    """电池流水数据访问"""

    model_class = BatteryLedger

    async def list_by_user(
        self, user_id: str, *, offset: int = 0, limit: int = 50
    ) -> list[BatteryLedger]:
        """查询某用户的电池流水（按时间降序）"""
        return await self.list_all(
            filters=[BatteryLedger.user_id == user_id],
            order_by=BatteryLedger.created_at.desc(),
            offset=offset,
            limit=limit,
        )


class MembershipOrderRepository(BaseRepository[MembershipOrder]):
    """会员订单数据访问"""

    model_class = MembershipOrder

    async def list_by_user(
        self, user_id: str, *, offset: int = 0, limit: int = 50
    ) -> list[MembershipOrder]:
        """查询某用户的套餐订单"""
        return await self.list_all(
            filters=[MembershipOrder.user_id == user_id],
            order_by=MembershipOrder.created_at.desc(),
            offset=offset,
            limit=limit,
        )
