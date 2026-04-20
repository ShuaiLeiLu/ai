"""
计费领域服务

双模式运行：
  1. 数据库模式（async）：通过 BatteryLedgerRepository 操作 PostgreSQL
  2. 内存 mock 模式（sync）：数据库未就绪时的降级方案
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.schemas import BatteryLedgerItem, BatteryPackage, MembershipInfo
from app.repositories.billing_repo import BatteryLedgerRepository


class BillingService:
    """会员与电池账本服务 —— 同时支持数据库和内存 mock 两种模式。"""

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
        self._membership = MembershipInfo(
            level="VIP1",
            display_name="基础会员",
            battery_discount=0.95,
            unlocked_features=["高级研究报告", "更多并发任务", "优先支持"],
        )
        self._ledger: list[BatteryLedgerItem] = [
            BatteryLedgerItem(
                item_id="bl_1",
                change=+1000,
                reason="购买基础包",
                created_at=now - timedelta(days=2),
            ),
            BatteryLedgerItem(
                item_id="bl_2",
                change=-120,
                reason="执行盘前速览任务",
                created_at=now - timedelta(hours=6),
            ),
        ]
        self._packages: list[BatteryPackage] = [
            BatteryPackage(package_id="pkg_basic", name="基础包", battery_count=1000, price=99.0),
            BatteryPackage(package_id="pkg_pro", name="专业包", battery_count=5000, price=459.0),
            BatteryPackage(package_id="pkg_flagship", name="旗舰包", battery_count=12000, price=999.0),
        ]

    def get_membership(self) -> MembershipInfo:
        return self._membership

    def list_ledger(self, limit: int = 50) -> list[BatteryLedgerItem]:
        sorted_ledger = sorted(
            self._ledger,
            key=lambda item: (item.created_at, item.item_id),
            reverse=True,
        )
        return sorted_ledger[:limit]

    def list_packages(self) -> list[BatteryPackage]:
        return self._packages

    # ──────────── 数据库模式（async） ────────────

    async def async_list_ledger(
        self, session: AsyncSession, user_id: str, *, limit: int = 50
    ) -> list[BatteryLedgerItem]:
        """从数据库查询电池流水"""
        repo = BatteryLedgerRepository(session)
        records = await repo.list_by_user(user_id, limit=limit)
        return [
            BatteryLedgerItem(
                item_id=r.id,
                change=r.change,
                reason=r.reason,
                created_at=r.created_at,
            )
            for r in records
        ]
