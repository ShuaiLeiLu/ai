"""
模拟交易引擎

功能：
  - 模拟账户管理（初始 100 万可用资金）
  - 下单撮合（买入扣减资金增加持仓 / 卖出释放资金减少持仓）
  - 持仓盈亏与账户汇总实时计算
  - 成交记录回放（计算已实现盈亏 / 持仓成本 / 历史统计）
"""
from __future__ import annotations

import json
import math
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
import time
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.client import (
    StockQuote,
    get_stock_quote_by_symbols,
    peek_stock_quote_by_symbols,
    run_sync,
)
from app.models.trading import Position as PositionModel
from app.models.trading import TradeLog as TradeLogModel
from app.models.trading import TradeRecord as RecordModel
from app.models.trading import TradingAccount as AccountModel
from app.modules.trading.schemas import (
    DEFAULT_INITIAL_CAPITAL,
    DailyReturn,
    EquityPoint,
    MonthlyReturn,
    PlaceOrderRequest,
    PlaceOrderResponse,
    PositionItem,
    RiskMetrics,
    TradeLogItem,
    TradeRecord,
    TradingAccount,
    TradingStreamSnapshot,
    TradingStats,
)
from app.repositories.trading_repo import PositionRepository, TradingAccountRepository

OPEN_COMMISSION_RATE = 0.0003
CLOSE_COMMISSION_RATE = 0.0003
CLOSE_TAX_RATE = 0.001
MIN_COMMISSION = 5.0
ACCOUNT_CACHE_TTL_SECONDS = 10
POSITIONS_CACHE_TTL_SECONDS = 10
STATS_CACHE_TTL_SECONDS = 60
ACCOUNT_ID_CACHE_TTL_SECONDS = 300


@dataclass
class _TimedCacheEntry:
    data: object
    expires_at: float


_view_cache: dict[str, _TimedCacheEntry] = {}


@dataclass
class _Lot:
    quantity: int
    unit_cost: float
    bought_at: datetime


@dataclass
class _ReplaySnapshot:
    record_map: dict[str, TradeRecord]
    daily_equity: dict[str, float]
    sell_pnls: list[float]
    hold_days: list[float]


class TradingService:
    """模拟交易引擎 —— 数据库持久化模式。"""

    @staticmethod
    def _cache_get(key: str) -> object | None:
        entry = _view_cache.get(key)
        if entry is None:
            return None
        if time.monotonic() > entry.expires_at:
            _view_cache.pop(key, None)
            return None
        return entry.data

    @staticmethod
    def _cache_set(key: str, data: object, ttl_seconds: int) -> None:
        _view_cache[key] = _TimedCacheEntry(
            data=data,
            expires_at=time.monotonic() + ttl_seconds,
        )

    @staticmethod
    def _cache_invalidate(prefixes: list[str]) -> None:
        for key in list(_view_cache.keys()):
            if any(key.startswith(prefix) for prefix in prefixes):
                _view_cache.pop(key, None)

    def empty_account(self) -> TradingAccount:
        """返回空账户快照，用于 researcher_id 缺失或 DB 不可用时兜底。"""
        return TradingAccount(
            account_id="acct_empty",
            initial_capital=DEFAULT_INITIAL_CAPITAL,
            total_asset=DEFAULT_INITIAL_CAPITAL,
            available_cash=DEFAULT_INITIAL_CAPITAL,
            holding_value=0.0,
            daily_pnl=0.0,
        )

    @staticmethod
    def _trade_fee(side: str, amount: float) -> float:
        """计算交易费用。

        规则与策略引擎保持一致：
        - 买入：佣金万三，最低 5 元
        - 卖出：佣金万三 + 印花税千一，最低佣金 5 元
        """
        if amount <= 0:
            return 0.0
        if side == "buy":
            return round(max(amount * OPEN_COMMISSION_RATE, MIN_COMMISSION), 2)
        commission = max(amount * CLOSE_COMMISSION_RATE, MIN_COMMISSION)
        tax = amount * CLOSE_TAX_RATE
        return round(commission + tax, 2)

    @staticmethod
    def _sort_positions(items: list[PositionItem]) -> list[PositionItem]:
        return sorted(items, key=lambda item: (abs(item.pnl), item.pnl, item.symbol), reverse=True)

    @staticmethod
    def _infer_initial_capital(account: AccountModel | object | None) -> float:
        """统一返回模拟盘初始资金口径。"""
        return DEFAULT_INITIAL_CAPITAL

    async def _resolve_account_model(
        self,
        session: AsyncSession,
        user_id: str,
        researcher_id: str,
    ) -> AccountModel:
        repo = TradingAccountRepository(session)
        acc = await repo.get_by_user_researcher(user_id, researcher_id)
        if not acc:
            acc = await repo.get_by_researcher(researcher_id)
        if not acc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模拟账户不存在")
        return acc

    async def async_resolve_account_id(
        self,
        session: AsyncSession,
        user_id: str,
        researcher_id: str,
    ) -> str:
        """解析研究员对应的模拟账户 ID，并做短缓存。

        交易详情页会在短时间内连续请求 account / positions / logs / stats，
        researcher -> account_id 的映射基本不变，没必要每个接口都重复查库。
        """
        cache_key = f"account-id:{user_id}:{researcher_id}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, str) and cached:
            return cached

        account = await self._resolve_account_model(session, user_id, researcher_id)
        self._cache_set(cache_key, account.id, ACCOUNT_ID_CACHE_TTL_SECONDS)
        return account.id

    @staticmethod
    def _apply_quotes_to_positions(
        positions: list[PositionModel],
        quote_map: dict[str, StockQuote],
    ) -> tuple[float, float]:
        """按最新行情盯市持仓，返回持仓市值与当日浮动盈亏。

        说明：
        - `pnl` 口径：持仓浮盈浮亏 = (最新价 - 成本价) * 持仓数量
        - `daily_pnl` 浮动部分口径： (最新价 - 昨收) * 持仓数量
        """
        holding_value = 0.0
        floating_daily_pnl = 0.0

        for position in positions:
            latest_price = float(position.current_price)
            quote = quote_map.get(position.symbol)
            if quote and float(quote.price) > 0:
                latest_price = float(quote.price)

            quantity = int(position.quantity)
            cost_price = float(position.cost_price)
            position.current_price = round(latest_price, 4)
            position.pnl = round((latest_price - cost_price) * quantity, 2)

            holding_value += latest_price * quantity

            if quote and float(quote.prev_close) > 0:
                floating_daily_pnl += (latest_price - float(quote.prev_close)) * quantity

        return round(holding_value, 2), round(floating_daily_pnl, 2)

    async def _load_realtime_quotes(
        self,
        symbols: list[str],
        *,
        cache_only: bool = False,
    ) -> dict[str, StockQuote]:
        """批量获取实时行情。

        - `cache_only=True`：只读本地缓存，不触发慢速的全市场行情拉取
        - `cache_only=False`：必要时触发外部行情拉取，适合 SSE 等实时流
        """
        normalized_symbols = sorted({symbol for symbol in symbols if symbol})
        if not normalized_symbols:
            return {}
        try:
            loader = peek_stock_quote_by_symbols if cache_only else get_stock_quote_by_symbols
            return await run_sync(loader, normalized_symbols)
        except Exception:
            return {}

    async def _load_account_records(self, session: AsyncSession, account_id: str) -> list[RecordModel]:
        stmt = (
            select(RecordModel)
            .where(RecordModel.account_id == account_id)
            .order_by(RecordModel.created_at.asc(), RecordModel.id.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _load_account_records_in_range(
        self,
        session: AsyncSession,
        account_id: str,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[RecordModel]:
        """按时间范围查询成交记录。

        账户概况的“今日盈亏”只关心当日成交，不应该每次都全量回放历史记录。
        这里先查当天窗口，只有确实存在卖出单时，才退化到全量回放计算真实已实现盈亏。
        """
        stmt = (
            select(RecordModel)
            .where(
                RecordModel.account_id == account_id,
                RecordModel.created_at >= start_at,
                RecordModel.created_at < end_at,
            )
            .order_by(RecordModel.created_at.asc(), RecordModel.id.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    def _replay_records(
        self,
        records: list[RecordModel],
        *,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ) -> _ReplaySnapshot:
        """按成交记录回放账户状态，生成可复用的增强数据。

        这一步统一负责：
        - 每笔卖出的真实成本价 / 已实现盈亏 / 盈亏比例
        - 每日权益曲线
        - 平均持仓天数、胜率等统计基础数据
        """
        lots: dict[str, deque[_Lot]] = defaultdict(deque)
        market_price: dict[str, float] = {}
        record_map: dict[str, TradeRecord] = {}
        daily_equity: dict[str, float] = {}
        sell_pnls: list[float] = []
        hold_days: list[float] = []
        cash = float(initial_capital)

        for row in records:
            price = float(row.price)
            quantity = int(row.quantity)
            amount = round(price * quantity, 2)
            commission = round(float(getattr(row, "commission", 0.0) or 0.0), 2)
            symbol = row.symbol
            name = getattr(row, "name", "") or ""
            dt = row.created_at

            cost_price: float | None = None
            realized_pnl: float | None = None
            realized_pnl_pct: float | None = None
            hold_days_val: float | None = None

            if row.side == "buy":
                cash -= amount + commission
                cost_price = round((amount + commission) / quantity, 4)
                lots[symbol].append(_Lot(quantity=quantity, unit_cost=cost_price, bought_at=dt))
                market_price[symbol] = price
            else:
                cash += amount - commission
                remaining = quantity
                cost_basis = 0.0
                weighted_hold_days = 0.0
                consumed = 0

                symbol_lots = lots[symbol]
                while remaining > 0 and symbol_lots:
                    lot = symbol_lots[0]
                    take = min(remaining, lot.quantity)
                    cost_basis += lot.unit_cost * take
                    weighted_hold_days += take * max((dt - lot.bought_at).total_seconds() / 86400, 0)
                    consumed += take
                    lot.quantity -= take
                    remaining -= take
                    if lot.quantity == 0:
                        symbol_lots.popleft()

                if remaining > 0:
                    # 容错：若出现超卖数据，避免把收益算成异常高值。
                    fallback_cost = price * remaining
                    cost_basis += fallback_cost
                    consumed += remaining

                if symbol_lots:
                    market_price[symbol] = price
                else:
                    market_price.pop(symbol, None)

                cost_price = round(cost_basis / quantity, 4) if quantity > 0 else None
                realized_pnl = round(amount - commission - cost_basis, 2)
                realized_pnl_pct = round(realized_pnl / cost_basis, 4) if cost_basis > 0 else None
                hold_days_val = round(weighted_hold_days / consumed, 1) if consumed > 0 else None

                sell_pnls.append(realized_pnl)
                if hold_days_val is not None:
                    hold_days.append(hold_days_val)

            holding_value = 0.0
            for holding_symbol, holding_lots in lots.items():
                total_qty = sum(lot.quantity for lot in holding_lots)
                if total_qty <= 0:
                    continue
                holding_value += market_price.get(holding_symbol, 0.0) * total_qty

            daily_equity[dt.strftime("%Y-%m-%d")] = round(cash + holding_value, 2)

            record_map[row.id] = TradeRecord(
                trade_id=row.id,
                symbol=symbol,
                name=name,
                side=row.side,
                quantity=quantity,
                price=price,
                amount=amount,
                commission=commission,
                cost_price=cost_price,
                realized_pnl=realized_pnl,
                realized_pnl_pct=realized_pnl_pct,
                hold_days=hold_days_val,
                created_at=dt,
            )

        return _ReplaySnapshot(
            record_map=record_map,
            daily_equity=daily_equity,
            sell_pnls=sell_pnls,
            hold_days=hold_days,
        )

    async def _refresh_account_snapshot(
        self,
        session: AsyncSession,
        account: AccountModel,
        *,
        cache_only: bool = True,
    ) -> None:
        """根据行情重算账户汇总。

        默认走缓存快路径；SSE 场景可显式要求走实时行情。
        """
        repo = PositionRepository(session)
        positions = await repo.list_by_account(account.id)
        quote_map = await self._load_realtime_quotes(
            [position.symbol for position in positions],
            cache_only=cache_only,
        )
        account.holding_value, floating_daily_pnl = self._apply_quotes_to_positions(positions, quote_map)
        account.total_asset = round(float(account.available_cash) + float(account.holding_value), 2)

        today = datetime.now().date()
        start_at = datetime.combine(today, datetime.min.time())
        end_at = start_at + timedelta(days=1)
        today_records = await self._load_account_records_in_range(
            session,
            account.id,
            start_at=start_at,
            end_at=end_at,
        )

        realized_daily_pnl = 0.0
        if today_records:
            if any(row.side == "sell" for row in today_records):
                # 只有当日存在卖出时，才需要回放全量历史去还原真实成本价。
                records = await self._load_account_records(session, account.id)
                replay = self._replay_records(records)
                for record in replay.record_map.values():
                    if record.created_at.date() != today:
                        continue
                    if record.side == "buy":
                        realized_daily_pnl -= record.commission
                    elif record.realized_pnl is not None:
                        realized_daily_pnl += record.realized_pnl
            else:
                realized_daily_pnl = -sum(float(row.commission or 0.0) for row in today_records)
        account.daily_pnl = round(realized_daily_pnl + floating_daily_pnl, 2)

    async def async_get_stream_snapshot(
        self,
        session: AsyncSession,
        user_id: str,
        researcher_id: str,
        *,
        cache_only: bool = False,
    ) -> TradingStreamSnapshot:
        """构建 SSE 推送用的交易实时快照。"""
        account = await self._resolve_account_model(session, user_id, researcher_id)
        await self._refresh_account_snapshot(session, account, cache_only=cache_only)
        positions = await self.async_list_positions(session, account.id, cache_only=cache_only)
        await session.flush()
        return TradingStreamSnapshot(
            generated_at=datetime.now(),
            account=TradingAccount(
                account_id=account.id,
                initial_capital=self._infer_initial_capital(account),
                total_asset=float(account.total_asset),
                available_cash=float(account.available_cash),
                holding_value=float(account.holding_value),
                daily_pnl=float(account.daily_pnl),
            ),
            positions=positions,
        )

    async def async_get_account(
        self, session: AsyncSession, user_id: str, researcher_id: str
    ) -> TradingAccount:
        """从数据库查询模拟账户。"""
        cache_key = f"account:{user_id}:{researcher_id}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, TradingAccount):
            return cached

        acc = await self._resolve_account_model(session, user_id, researcher_id)

        await self._refresh_account_snapshot(session, acc, cache_only=True)
        await session.flush()

        data = TradingAccount(
            account_id=acc.id,
            initial_capital=self._infer_initial_capital(acc),
            total_asset=float(acc.total_asset),
            available_cash=float(acc.available_cash),
            holding_value=float(acc.holding_value),
            daily_pnl=float(acc.daily_pnl),
        )
        self._cache_set(cache_key, data, ACCOUNT_CACHE_TTL_SECONDS)
        return data

    async def async_list_positions(
        self,
        session: AsyncSession,
        account_id: str,
        *,
        cache_only: bool = True,
    ) -> list[PositionItem]:
        """从数据库查询持仓，并尽量用实时行情更新 current_price / pnl。

        默认走缓存快路径，避免普通 REST 接口被实时行情外部请求拖慢。
        """
        if cache_only:
            cache_key = f"positions:{account_id}"
            cached = self._cache_get(cache_key)
            if isinstance(cached, list):
                return cached

        repo = PositionRepository(session)
        positions = await repo.list_by_account(account_id)
        quote_map = await self._load_realtime_quotes(
            [position.symbol for position in positions],
            cache_only=cache_only,
        )
        self._apply_quotes_to_positions(positions, quote_map)
        items = [
            PositionItem(
                symbol=position.symbol,
                name=position.name,
                quantity=position.quantity,
                cost_price=float(position.cost_price),
                current_price=float(position.current_price),
                pnl=float(position.pnl),
            )
            for position in positions
        ]
        sorted_items = self._sort_positions(items)
        if cache_only:
            self._cache_set(f"positions:{account_id}", sorted_items, POSITIONS_CACHE_TTL_SECONDS)
        return sorted_items

    async def async_list_records(
        self, session: AsyncSession, account_id: str, *, limit: int = 20
    ) -> list[TradeRecord]:
        """从数据库查询成交记录，并补齐成本/已实现盈亏等增强字段。"""
        records = await self._load_account_records(session, account_id)
        replay = self._replay_records(records)
        desc_items = [replay.record_map[row.id] for row in reversed(records)]
        return desc_items[:limit]

    async def async_list_logs(
        self, session: AsyncSession, account_id: str, *, limit: int = 100
    ) -> list[TradeLogItem]:
        """从数据库查询交易日志（trade + analysis 条目），并填充增强后的成交记录。"""
        stmt = (
            select(TradeLogModel)
            .where(TradeLogModel.account_id == account_id)
            .order_by(TradeLogModel.created_at.asc(), TradeLogModel.id.asc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        logs = list(result.scalars().all())

        records = await self._load_account_records(session, account_id)
        replay = self._replay_records(records)

        items: list[TradeLogItem] = []
        for log in logs:
            try:
                record_ids = json.loads(log.trade_record_ids or "[]")
            except Exception:
                record_ids = []
            related_records = [replay.record_map[record_id] for record_id in record_ids if record_id in replay.record_map]
            items.append(
                TradeLogItem(
                    log_id=log.id,
                    log_type=log.log_type,
                    trade_records=related_records,
                    title=log.title or "",
                    content=log.content or "",
                    created_at=log.created_at,
                )
            )
        return items

    async def async_get_stats(
        self, session: AsyncSession, account_id: str, initial_capital: float | None = None
    ) -> TradingStats:
        """从成交记录计算历史交易统计数据：收益曲线、月度收益、风控指标、日收益序列。"""
        cache_key = f"stats:{account_id}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, TradingStats):
            return cached

        acct_stmt = select(AccountModel).where(AccountModel.id == account_id)
        acct_result = await session.execute(acct_stmt)
        account = acct_result.scalar_one_or_none()
        initial_capital = initial_capital or self._infer_initial_capital(account)
        total_asset = float(account.total_asset) if account else initial_capital
        if account:
            await self._refresh_account_snapshot(session, account, cache_only=True)
            total_asset = float(account.total_asset)

        records = await self._load_account_records(session, account_id)
        if not records:
            data = TradingStats(
                initial_capital=initial_capital,
                total_asset=total_asset,
                equity_curve=[],
                monthly_returns=[],
                daily_returns=[],
                risk=RiskMetrics(
                    total_return=0,
                    annual_return=0,
                    max_drawdown=0,
                    sharpe=0,
                    win_rate=0,
                    profit_loss_ratio=0,
                    total_trades=0,
                    win_trades=0,
                    lose_trades=0,
                    max_profit=0,
                    max_loss=0,
                    avg_hold_days=0,
                ),
            )
            self._cache_set(cache_key, data, STATS_CACHE_TTL_SECONDS)
            return data

        replay = self._replay_records(records, initial_capital=initial_capital)
        daily_equity = dict(replay.daily_equity)
        today_str = datetime.now().date().strftime("%Y-%m-%d")
        if today_str not in daily_equity:
            daily_equity[today_str] = round(total_asset, 2)

        sorted_dates = sorted(daily_equity.keys())
        equity_curve = [EquityPoint(date=date, equity=round(daily_equity[date], 2)) for date in sorted_dates]

        daily_returns: list[DailyReturn] = []
        previous_equity = initial_capital
        for date in sorted_dates:
            equity = daily_equity[date]
            pnl = equity - previous_equity
            daily_returns.append(DailyReturn(date=date, pnl=round(pnl, 2)))
            previous_equity = equity

        monthly_map: dict[str, float] = defaultdict(float)
        monthly_base: dict[str, float] = {}
        previous_equity = initial_capital
        for date in sorted_dates:
            month = date[:7]
            if month not in monthly_base:
                monthly_base[month] = previous_equity
            monthly_map[month] = daily_equity[date] - monthly_base[month]
            previous_equity = daily_equity[date]

        monthly_returns = [
            MonthlyReturn(
                month=month,
                pnl=round(monthly_map[month], 2),
                pct=round(monthly_map[month] / monthly_base[month], 4) if monthly_base.get(month) else 0,
            )
            for month in sorted(monthly_map.keys())
        ]

        total_return = (total_asset - initial_capital) / initial_capital if initial_capital > 0 else 0
        trading_days = max(len(sorted_dates), 1)
        annual_return = total_return * (252 / trading_days)

        peak = initial_capital
        max_drawdown = 0.0
        for date in sorted_dates:
            equity = daily_equity[date]
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else 0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        daily_ret_series: list[float] = []
        previous_equity = initial_capital
        for date in sorted_dates:
            equity = daily_equity[date]
            daily_ret_series.append((equity - previous_equity) / previous_equity if previous_equity > 0 else 0)
            previous_equity = equity
        avg_ret = sum(daily_ret_series) / len(daily_ret_series) if daily_ret_series else 0
        std_ret = (
            sum((value - avg_ret) ** 2 for value in daily_ret_series) / len(daily_ret_series)
        ) ** 0.5 if daily_ret_series else 0
        sharpe = (avg_ret / std_ret * math.sqrt(252)) if std_ret > 0 else 0

        sell_pnls = replay.sell_pnls
        win_count = sum(1 for pnl in sell_pnls if pnl > 0)
        lose_count = sum(1 for pnl in sell_pnls if pnl < 0)
        total_trades = len(sell_pnls)
        profits = [pnl for pnl in sell_pnls if pnl > 0]
        losses = [abs(pnl) for pnl in sell_pnls if pnl < 0]
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0

        risk = RiskMetrics(
            total_return=round(total_return, 4),
            annual_return=round(annual_return, 4),
            max_drawdown=round(-max_drawdown, 4),
            sharpe=round(sharpe, 2),
            win_rate=round(win_count / total_trades, 4) if total_trades > 0 else 0,
            profit_loss_ratio=round(profit_loss_ratio, 2),
            total_trades=total_trades,
            win_trades=win_count,
            lose_trades=lose_count,
            max_profit=round(max(profits), 2) if profits else 0,
            max_loss=round(max(losses), 2) if losses else 0,
            avg_hold_days=round(sum(replay.hold_days) / len(replay.hold_days), 1) if replay.hold_days else 0,
        )

        data = TradingStats(
            initial_capital=initial_capital,
            total_asset=round(total_asset, 2),
            equity_curve=equity_curve,
            monthly_returns=monthly_returns,
            daily_returns=daily_returns,
            risk=risk,
        )
        self._cache_set(cache_key, data, STATS_CACHE_TTL_SECONDS)
        return data

    async def async_place_order(
        self, session: AsyncSession, user_id: str, payload: PlaceOrderRequest
    ) -> PlaceOrderResponse:
        """数据库模式下单撮合。

        买入：
        - 检查可用资金 >= 成交金额 + 手续费
        - 更新持仓成本
        - 账户当日盈亏扣除买入手续费

        卖出：
        - 检查持仓数量
        - 释放净资金（卖出金额 - 手续费 - 印花税）
        - 账户当日盈亏计入已实现盈亏
        """
        acct_repo = TradingAccountRepository(session)
        pos_repo = PositionRepository(session)

        acc = await acct_repo.get_by_user_researcher(user_id, payload.researcher_id)
        if not acc:
            acc = await acct_repo.get_by_researcher(payload.researcher_id)
        if not acc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模拟账户不存在")

        amount = round(payload.price * payload.quantity, 2)
        commission = self._trade_fee(payload.side, amount)
        trade_id = f"trd_{uuid4().hex[:8]}"

        if payload.side == "buy":
            total_cost = amount + commission
            if float(acc.available_cash) < total_cost:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"可用资金不足：需要 {total_cost:.2f}，当前 {float(acc.available_cash):.2f}",
                )

            acc.available_cash = round(float(acc.available_cash) - total_cost, 2)
            acc.daily_pnl = round(float(acc.daily_pnl) - commission, 2)

            existing = await pos_repo.get_by_account_symbol(acc.id, payload.symbol)
            unit_cost = total_cost / payload.quantity
            if existing:
                new_qty = existing.quantity + payload.quantity
                new_cost = ((float(existing.cost_price) * existing.quantity) + total_cost) / new_qty
                existing.quantity = new_qty
                existing.cost_price = round(new_cost, 4)
                existing.current_price = payload.price
                existing.pnl = round((payload.price - new_cost) * new_qty, 2)
            else:
                session.add(
                    PositionModel(
                        id=f"pos_{uuid4().hex[:8]}",
                        account_id=acc.id,
                        symbol=payload.symbol,
                        name=payload.name or payload.symbol,
                        quantity=payload.quantity,
                        cost_price=round(unit_cost, 4),
                        current_price=payload.price,
                        pnl=round((payload.price - unit_cost) * payload.quantity, 2),
                    )
                )
            message = f"买入成功：{payload.symbol} {payload.quantity}股 @ {payload.price}"
        else:
            existing = await pos_repo.get_by_account_symbol(acc.id, payload.symbol)
            available_qty = existing.quantity if existing else 0
            if available_qty < payload.quantity:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"持仓不足：可卖 {available_qty} 股",
                )

            net_amount = amount - commission
            realized_pnl = round(net_amount - float(existing.cost_price) * payload.quantity, 2)
            acc.available_cash = round(float(acc.available_cash) + net_amount, 2)
            acc.daily_pnl = round(float(acc.daily_pnl) + realized_pnl, 2)

            new_qty = existing.quantity - payload.quantity
            if new_qty == 0:
                await session.delete(existing)
            else:
                existing.quantity = new_qty
                existing.current_price = payload.price
                existing.pnl = round((payload.price - float(existing.cost_price)) * new_qty, 2)
            message = f"卖出成功：{payload.symbol} {payload.quantity}股 @ {payload.price}"

        session.add(
            RecordModel(
                id=trade_id,
                account_id=acc.id,
                symbol=payload.symbol,
                name=payload.name or payload.symbol,
                side=payload.side,
                quantity=payload.quantity,
                price=payload.price,
                commission=commission,
            )
        )
        session.add(
            TradeLogModel(
                id=f"tl_{uuid4().hex[:8]}",
                account_id=acc.id,
                log_type="trade",
                trade_record_ids=json.dumps([trade_id]),
                title="",
                content="",
            )
        )

        await self._refresh_account_snapshot(session, acc)
        await session.commit()
        self._cache_invalidate(
            [
                f"account:{user_id}:{payload.researcher_id}",
                f"positions:{acc.id}",
                f"stats:{acc.id}",
            ]
        )

        return PlaceOrderResponse(
            trade_id=trade_id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            price=payload.price,
            amount=amount,
            message=message,
        )
