"""
模拟交易引擎

功能：
  - 模拟账户管理（初始 100 万可用资金）
  - 下单撮合（买入扣减资金增加持仓 / 卖出释放资金减少持仓）
  - 持仓盈亏实时计算
  - 账户资产自动更新
  - 双模式：内存 mock + async 数据库

撮合规则（简化版）：
  - 限价单即时成交（模拟环境，不做竞价撮合）
  - 买入：可用资金 >= 成交金额
  - 卖出：持仓数量 >= 卖出数量
  - 手续费暂不计算
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trading import Position as PositionModel
from app.models.trading import TradingAccount as AccountModel
from app.models.trading import TradeRecord as RecordModel
from app.modules.trading.schemas import (
    PlaceOrderRequest,
    PlaceOrderResponse,
    PositionItem,
    TradeRecord,
    TradingAccount,
)
from app.repositories.trading_repo import PositionRepository, TradingAccountRepository, TradeRecordRepository


class TradingService:
    """模拟交易引擎 —— 内存撮合 + 数据库持久化双模式。"""

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
        # ── 内存 mock 数据 ──
        self._account = TradingAccount(
            account_id="sim_account_1",
            total_asset=1004270.0,
            available_cash=706120.0,
            holding_value=298150.0,
            daily_pnl=2270.0,
        )
        self._positions: dict[str, PositionItem] = {
            "300183": PositionItem(
                symbol="300183",
                name="东软载波",
                quantity=6700,
                cost_price=14.88,
                current_price=15.48,
                pnl=4020.0,
            ),
            "002533": PositionItem(
                symbol="002533",
                name="金杯电工",
                quantity=7200,
                cost_price=13.75,
                current_price=13.67,
                pnl=-576.0,
            ),
        }
        self._records: list[TradeRecord] = [
            TradeRecord(
                trade_id="trd_1",
                symbol="300183",
                side="buy",
                quantity=1200,
                price=15.12,
                amount=1200 * 15.12,
                created_at=now - timedelta(hours=3),
            )
        ]

    # ──────────── 内存 mock 模式 ────────────

    def get_account(self) -> TradingAccount:
        """获取账户概况"""
        return self._account

    def list_positions(self) -> list[PositionItem]:
        """持仓列表（按盈亏绝对值排序）"""
        return sorted(
            self._positions.values(),
            key=lambda p: (abs(p.pnl), p.pnl, p.symbol),
            reverse=True,
        )

    def list_records(self, limit: int = 20) -> list[TradeRecord]:
        """成交记录（按时间降序）"""
        sorted_records = sorted(
            self._records,
            key=lambda r: (r.created_at, r.trade_id),
            reverse=True,
        )
        return sorted_records[:limit]

    def place_order(self, payload: PlaceOrderRequest) -> PlaceOrderResponse:
        """模拟下单撮合（内存模式）

        买入：检查资金 → 扣减资金 → 增加/新建持仓
        卖出：检查持仓 → 释放资金 → 减少/清除持仓
        """
        amount = payload.price * payload.quantity
        now = datetime.now(tz=UTC)
        trade_id = f"trd_{uuid4().hex[:8]}"

        if payload.side == "buy":
            # 检查资金
            if self._account.available_cash < amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"可用资金不足：需要 {amount:.2f}，当前 {self._account.available_cash:.2f}",
                )
            # 扣减资金
            self._account = TradingAccount(
                account_id=self._account.account_id,
                total_asset=self._account.total_asset,
                available_cash=self._account.available_cash - amount,
                holding_value=self._account.holding_value + amount,
                daily_pnl=self._account.daily_pnl,
            )
            # 更新持仓
            existing = self._positions.get(payload.symbol)
            if existing:
                new_qty = existing.quantity + payload.quantity
                new_cost = (existing.cost_price * existing.quantity + amount) / new_qty
                self._positions[payload.symbol] = PositionItem(
                    symbol=payload.symbol,
                    name=payload.name or existing.name,
                    quantity=new_qty,
                    cost_price=round(new_cost, 4),
                    current_price=payload.price,
                    pnl=round((payload.price - new_cost) * new_qty, 2),
                )
            else:
                self._positions[payload.symbol] = PositionItem(
                    symbol=payload.symbol,
                    name=payload.name or payload.symbol,
                    quantity=payload.quantity,
                    cost_price=payload.price,
                    current_price=payload.price,
                    pnl=0.0,
                )
            message = f"买入成功：{payload.symbol} {payload.quantity}股 @ {payload.price}"

        else:  # sell
            existing = self._positions.get(payload.symbol)
            if not existing or existing.quantity < payload.quantity:
                available = existing.quantity if existing else 0
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"持仓不足：可卖 {available} 股",
                )
            # 释放资金
            self._account = TradingAccount(
                account_id=self._account.account_id,
                total_asset=self._account.total_asset + (payload.price - existing.cost_price) * payload.quantity,
                available_cash=self._account.available_cash + amount,
                holding_value=self._account.holding_value - existing.cost_price * payload.quantity,
                daily_pnl=self._account.daily_pnl + (payload.price - existing.cost_price) * payload.quantity,
            )
            # 更新持仓
            new_qty = existing.quantity - payload.quantity
            if new_qty == 0:
                del self._positions[payload.symbol]
            else:
                self._positions[payload.symbol] = PositionItem(
                    symbol=payload.symbol,
                    name=existing.name,
                    quantity=new_qty,
                    cost_price=existing.cost_price,
                    current_price=payload.price,
                    pnl=round((payload.price - existing.cost_price) * new_qty, 2),
                )
            message = f"卖出成功：{payload.symbol} {payload.quantity}股 @ {payload.price}"

        # 记录成交
        record = TradeRecord(
            trade_id=trade_id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            amount=amount,
            created_at=now,
        )
        self._records.append(record)

        return PlaceOrderResponse(
            trade_id=trade_id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            amount=amount,
            message=message,
        )

    # ──────────── 数据库模式（async） ────────────

    async def async_get_account(
        self, session: AsyncSession, user_id: str, researcher_id: str
    ) -> TradingAccount:
        """从数据库查询模拟账户。

        查询顺序：
          1. 先按 user_id + researcher_id 查（用户私有账户）
          2. 查不到则按 researcher_id 查（系统内定研究员的共享账户）
        """
        repo = TradingAccountRepository(session)
        acc = await repo.get_by_user_researcher(user_id, researcher_id)
        if not acc:
            # 系统研究员的账户绑定在 seed 用户名下，按 researcher_id 兜底
            acc = await repo.get_by_researcher(researcher_id)
        if not acc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模拟账户不存在")
        return TradingAccount(
            account_id=acc.id,
            total_asset=float(acc.total_asset),
            available_cash=float(acc.available_cash),
            holding_value=float(acc.holding_value),
            daily_pnl=float(acc.daily_pnl),
        )

    async def async_list_positions(self, session: AsyncSession, account_id: str) -> list[PositionItem]:
        """从数据库查询持仓"""
        repo = PositionRepository(session)
        positions = await repo.list_by_account(account_id)
        return [
            PositionItem(
                symbol=p.symbol,
                name=p.name,
                quantity=p.quantity,
                cost_price=float(p.cost_price),
                current_price=float(p.current_price),
                pnl=float(p.pnl),
            )
            for p in positions
        ]

    async def async_list_records(
        self, session: AsyncSession, account_id: str, *, limit: int = 20
    ) -> list[TradeRecord]:
        """从数据库查询成交记录"""
        repo = TradeRecordRepository(session)
        records = await repo.list_by_account(account_id, limit=limit)
        return [
            TradeRecord(
                trade_id=r.id,
                symbol=r.symbol,
                name=getattr(r, 'name', '') or '',
                side=r.side,
                quantity=r.quantity,
                price=float(r.price),
                amount=float(r.price) * r.quantity,
                commission=float(getattr(r, 'commission', 0) or 0),
                created_at=r.created_at,
            )
            for r in records
        ]

    async def async_list_logs(
        self, session: AsyncSession, account_id: str, *, limit: int = 100
    ) -> list["TradeLogItem"]:
        """从数据库查询交易日志（trade + analysis 条目），并填充关联的成交记录"""
        import json as _json
        from sqlalchemy import select as _select
        from app.models.trading import TradeLog as TradeLogModel
        from app.models.trading import TradeRecord as RecordModel
        from app.modules.trading.schemas import TradeLogItem

        stmt = (
            _select(TradeLogModel)
            .where(TradeLogModel.account_id == account_id)
            .order_by(TradeLogModel.created_at.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        logs = list(result.scalars().all())

        # 收集所有关联的 record ids，批量查询
        all_record_ids: set[str] = set()
        for log in logs:
            try:
                ids = _json.loads(log.trade_record_ids or "[]")
                all_record_ids.update(ids)
            except Exception:
                pass

        record_map: dict[str, "TradeRecord"] = {}
        if all_record_ids:
            rec_stmt = _select(RecordModel).where(RecordModel.id.in_(all_record_ids))
            rec_result = await session.execute(rec_stmt)
            for r in rec_result.scalars().all():
                record_map[r.id] = TradeRecord(
                    trade_id=r.id,
                    symbol=r.symbol,
                    name=getattr(r, 'name', '') or '',
                    side=r.side,
                    quantity=r.quantity,
                    price=float(r.price),
                    amount=float(r.price) * r.quantity,
                    commission=float(getattr(r, 'commission', 0) or 0),
                    created_at=r.created_at,
                )

        items: list[TradeLogItem] = []
        for log in logs:
            try:
                ids = _json.loads(log.trade_record_ids or "[]")
            except Exception:
                ids = []
            related_records = [record_map[rid] for rid in ids if rid in record_map]
            items.append(TradeLogItem(
                log_id=log.id,
                log_type=log.log_type,
                trade_records=related_records,
                title=log.title or "",
                content=log.content or "",
                created_at=log.created_at,
            ))
        return items

    async def async_get_stats(
        self, session: AsyncSession, account_id: str, initial_capital: float = 100_000
    ) -> "TradingStats":
        """从成交记录计算历史交易统计数据：收益曲线、月度收益、风控指标、日收益序列。"""
        import math
        from collections import defaultdict
        from sqlalchemy import select as _sel
        from app.modules.trading.schemas import (
            DailyReturn, EquityPoint, MonthlyReturn, RiskMetrics, TradingStats,
        )

        # 查询所有成交记录（按时间正序）
        stmt = (
            _sel(RecordModel)
            .where(RecordModel.account_id == account_id)
            .order_by(RecordModel.created_at.asc())
        )
        result = await session.execute(stmt)
        records = list(result.scalars().all())

        # 查询当前账户总资产
        acct_stmt = _sel(AccountModel).where(AccountModel.id == account_id)
        acct_result = await session.execute(acct_stmt)
        account = acct_result.scalar_one_or_none()
        total_asset = account.total_asset if account else initial_capital

        if not records:
            return TradingStats(
                initial_capital=initial_capital,
                total_asset=total_asset,
                equity_curve=[],
                monthly_returns=[],
                daily_returns=[],
                risk=RiskMetrics(
                    total_return=0, annual_return=0, max_drawdown=0, sharpe=0,
                    win_rate=0, profit_loss_ratio=0, total_trades=0,
                    win_trades=0, lose_trades=0, max_profit=0, max_loss=0,
                    avg_hold_days=0,
                ),
            )

        # ── 按日聚合计算净值曲线 ──
        # 用 "模拟持仓估值" 方式：逐笔追踪 cash + holdings
        daily_equity: dict[str, float] = {}
        daily_pnl_map: dict[str, float] = defaultdict(float)
        cash = initial_capital
        holdings: dict[str, dict] = {}  # symbol -> {qty, cost}

        prev_equity = initial_capital
        for r in records:
            dt_str = r.created_at.strftime("%Y-%m-%d")
            amount = float(r.price) * r.quantity
            commission = float(getattr(r, 'commission', 0) or 0)

            if r.side == "buy":
                cash -= amount + commission
                if r.symbol in holdings:
                    h = holdings[r.symbol]
                    total_qty = h["qty"] + r.quantity
                    h["cost"] = (h["cost"] * h["qty"] + amount) / total_qty if total_qty > 0 else 0
                    h["qty"] = total_qty
                else:
                    holdings[r.symbol] = {"qty": r.quantity, "cost": float(r.price)}
                holdings[r.symbol]["price"] = float(r.price)
            else:
                cash += amount - commission
                if r.symbol in holdings:
                    h = holdings[r.symbol]
                    pnl = (float(r.price) - h["cost"]) * r.quantity - commission
                    daily_pnl_map[dt_str] += pnl
                    h["qty"] -= r.quantity
                    if h["qty"] <= 0:
                        del holdings[r.symbol]
                    else:
                        h["price"] = float(r.price)

            # 估算当日权益
            holding_val = sum(h["price"] * h["qty"] for h in holdings.values())
            equity = cash + holding_val
            daily_equity[dt_str] = equity

        # 填充到当前日
        from datetime import date as _date
        today_str = _date.today().strftime("%Y-%m-%d")
        if today_str not in daily_equity:
            daily_equity[today_str] = total_asset

        sorted_dates = sorted(daily_equity.keys())

        # ── 收益曲线 ──
        equity_curve = [EquityPoint(date=d, equity=round(daily_equity[d], 2)) for d in sorted_dates]

        # ── 日收益序列 ──
        daily_returns: list[DailyReturn] = []
        prev_eq = initial_capital
        for d in sorted_dates:
            eq = daily_equity[d]
            pnl = eq - prev_eq
            daily_returns.append(DailyReturn(date=d, pnl=round(pnl, 2)))
            prev_eq = eq

        # ── 月度收益 ──
        monthly_map: dict[str, float] = defaultdict(float)
        monthly_base: dict[str, float] = {}
        prev_eq = initial_capital
        for d in sorted_dates:
            m = d[:7]
            if m not in monthly_base:
                monthly_base[m] = prev_eq
            monthly_map[m] = daily_equity[d] - monthly_base[m]
            prev_eq = daily_equity[d]

        monthly_returns = [
            MonthlyReturn(
                month=m,
                pnl=round(monthly_map[m], 2),
                pct=round(monthly_map[m] / monthly_base[m], 4) if monthly_base.get(m) else 0,
            )
            for m in sorted(monthly_map.keys())
        ]

        # ── 风控指标 ──
        total_return = (total_asset - initial_capital) / initial_capital if initial_capital > 0 else 0
        n_days = max(len(sorted_dates), 1)
        annual_return = total_return * (252 / n_days) if n_days > 0 else 0

        # 最大回撤
        peak = initial_capital
        max_dd = 0.0
        for d in sorted_dates:
            eq = daily_equity[d]
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # 日收益率序列 → 夏普比率
        daily_rets = []
        prev_eq = initial_capital
        for d in sorted_dates:
            eq = daily_equity[d]
            daily_rets.append((eq - prev_eq) / prev_eq if prev_eq > 0 else 0)
            prev_eq = eq
        avg_ret = sum(daily_rets) / len(daily_rets) if daily_rets else 0
        std_ret = (sum((r - avg_ret) ** 2 for r in daily_rets) / len(daily_rets)) ** 0.5 if daily_rets else 0
        sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0

        # 胜率 / 盈亏比（基于卖出记录）
        sell_pnls: list[float] = []
        for r in records:
            if r.side == "sell":
                # 从 daily_pnl_map 无法精确拆分，用 commission 近似
                pnl_est = float(r.price) * r.quantity - float(getattr(r, 'commission', 0) or 0)
                # 需要知道买入成本，这里简化：正 pnl 来自 pnl_map
                pass
        # 更精确的方式：遍历记录重新配对
        buy_cost_map: dict[str, float] = {}
        win_count = 0
        lose_count = 0
        profits: list[float] = []
        losses: list[float] = []
        max_profit = 0.0
        max_loss = 0.0
        for r in records:
            if r.side == "buy":
                buy_cost_map[r.symbol] = float(r.price)
            elif r.side == "sell":
                cost = buy_cost_map.get(r.symbol, float(r.price))
                pnl = (float(r.price) - cost) * r.quantity - float(getattr(r, 'commission', 0) or 0)
                if pnl >= 0:
                    win_count += 1
                    profits.append(pnl)
                    if pnl > max_profit:
                        max_profit = pnl
                else:
                    lose_count += 1
                    losses.append(abs(pnl))
                    if abs(pnl) > max_loss:
                        max_loss = abs(pnl)

        total_trades = win_count + lose_count
        win_rate = win_count / total_trades if total_trades > 0 else 0
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses) / len(losses) if losses else 1
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

        risk = RiskMetrics(
            total_return=round(total_return, 4),
            annual_return=round(annual_return, 4),
            max_drawdown=round(-max_dd, 4),
            sharpe=round(sharpe, 2),
            win_rate=round(win_rate, 4),
            profit_loss_ratio=round(profit_loss_ratio, 2),
            total_trades=total_trades,
            win_trades=win_count,
            lose_trades=lose_count,
            max_profit=round(max_profit, 2),
            max_loss=round(max_loss, 2),
            avg_hold_days=round(n_days / max(total_trades, 1), 1),
        )

        return TradingStats(
            initial_capital=initial_capital,
            total_asset=round(total_asset, 2),
            equity_curve=equity_curve,
            monthly_returns=monthly_returns,
            daily_returns=daily_returns,
            risk=risk,
        )

    async def async_place_order(
        self, session: AsyncSession, user_id: str, payload: PlaceOrderRequest
    ) -> PlaceOrderResponse:
        """数据库模式下单撮合。

        买入：检查可用资金 → 扣减资金 → 增加/新建持仓 → 写成交记录
        卖出：检查持仓数量 → 释放资金 → 减少/清除持仓 → 写成交记录
        """
        from app.modules.trading.schemas import PlaceOrderResponse as OrderResp

        acct_repo = TradingAccountRepository(session)
        pos_repo = PositionRepository(session)
        rec_repo = TradeRecordRepository(session)

        # 查找模拟账户（先按 user+researcher，再按 researcher 兜底）
        acc = await acct_repo.get_by_user_researcher(user_id, payload.researcher_id)
        if not acc:
            acc = await acct_repo.get_by_researcher(payload.researcher_id)
        if not acc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模拟账户不存在")

        amount = payload.price * payload.quantity
        trade_id = f"trd_{uuid4().hex[:8]}"

        if payload.side == "buy":
            # 检查资金
            if acc.available_cash < amount:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"可用资金不足：需要 {amount:.2f}，当前 {acc.available_cash:.2f}",
                )
            # 扣减资金
            acc.available_cash -= amount
            acc.holding_value += amount
            # 更新持仓
            existing = await pos_repo.get_by_account_symbol(acc.id, payload.symbol)
            if existing:
                new_qty = existing.quantity + payload.quantity
                new_cost = (existing.cost_price * existing.quantity + amount) / new_qty
                existing.quantity = new_qty
                existing.cost_price = round(new_cost, 4)
                existing.current_price = payload.price
                existing.pnl = round((payload.price - new_cost) * new_qty, 2)
            else:
                new_pos = PositionModel(
                    id=f"pos_{uuid4().hex[:8]}",
                    account_id=acc.id,
                    symbol=payload.symbol,
                    name=payload.name or payload.symbol,
                    quantity=payload.quantity,
                    cost_price=payload.price,
                    current_price=payload.price,
                    pnl=0.0,
                )
                session.add(new_pos)
            message = f"买入成功：{payload.symbol} {payload.quantity}股 @ {payload.price}"

        else:  # sell
            existing = await pos_repo.get_by_account_symbol(acc.id, payload.symbol)
            available_qty = existing.quantity if existing else 0
            if available_qty < payload.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"持仓不足：可卖 {available_qty} 股",
                )
            pnl = (payload.price - existing.cost_price) * payload.quantity
            # 释放资金
            acc.available_cash += amount
            acc.holding_value -= existing.cost_price * payload.quantity
            acc.total_asset += pnl
            acc.daily_pnl += pnl
            # 更新持仓
            new_qty = existing.quantity - payload.quantity
            if new_qty == 0:
                await session.delete(existing)
            else:
                existing.quantity = new_qty
                existing.current_price = payload.price
                existing.pnl = round((payload.price - existing.cost_price) * new_qty, 2)
            message = f"卖出成功：{payload.symbol} {payload.quantity}股 @ {payload.price}"

        # 写成交记录
        record = RecordModel(
            id=trade_id,
            account_id=acc.id,
            symbol=payload.symbol,
            name=payload.name or payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
        )
        session.add(record)
        await session.commit()

        return OrderResp(
            trade_id=trade_id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            amount=amount,
            message=message,
        )
