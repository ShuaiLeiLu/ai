"""
交易 Repository —— TradingAccount / Position / TradeRecord 表的数据访问层

提供：
  - 按用户+研究员查询模拟账户
  - 持仓列表
  - 成交记录列表
  - 排行榜查询（按总资产/今日收益排序）
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import Position, TradingAccount, TradeRecord
from app.repositories.base import BaseRepository


class TradingAccountRepository(BaseRepository[TradingAccount]):
    """模拟交易账户数据访问"""

    model_class = TradingAccount

    async def get_by_user_researcher(
        self, user_id: str, researcher_id: str
    ) -> TradingAccount | None:
        """按用户+研究员查找关联的模拟账户"""
        stmt = select(TradingAccount).where(
            TradingAccount.user_id == user_id,
            TradingAccount.researcher_id == researcher_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_researcher(self, researcher_id: str) -> TradingAccount | None:
        """按研究员ID查找模拟账户（系统研究员共享账户兜底）"""
        stmt = select(TradingAccount).where(
            TradingAccount.researcher_id == researcher_id,
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_user(self, user_id: str) -> list[TradingAccount]:
        """查询某用户的所有模拟账户"""
        return await self.list_all(
            filters=[TradingAccount.user_id == user_id],
            order_by=TradingAccount.created_at.desc(),
        )

    async def ranking_by_total_asset(self, *, limit: int = 10) -> list[TradingAccount]:
        """按总资产降序排行"""
        return await self.list_all(
            order_by=TradingAccount.total_asset.desc(),
            limit=limit,
        )

    async def ranking_by_daily_pnl(self, *, limit: int = 10) -> list[TradingAccount]:
        """按今日盈亏降序排行"""
        return await self.list_all(
            order_by=TradingAccount.daily_pnl.desc(),
            limit=limit,
        )


class PositionRepository(BaseRepository[Position]):
    """持仓数据访问"""

    model_class = Position

    async def get_by_account_symbol(self, account_id: str, symbol: str) -> Position | None:
        """按账户+股票代码查找单条持仓"""
        stmt = select(Position).where(
            Position.account_id == account_id,
            Position.symbol == symbol,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_account(self, account_id: str) -> list[Position]:
        """查询某账户的所有持仓"""
        return await self.list_all(
            filters=[Position.account_id == account_id],
        )


class TradeRecordRepository(BaseRepository[TradeRecord]):
    """成交记录数据访问"""

    model_class = TradeRecord

    async def list_by_account(
        self, account_id: str, *, offset: int = 0, limit: int = 50
    ) -> list[TradeRecord]:
        """查询某账户的成交记录"""
        return await self.list_all(
            filters=[TradeRecord.account_id == account_id],
            order_by=TradeRecord.created_at.desc(),
            offset=offset,
            limit=limit,
        )
