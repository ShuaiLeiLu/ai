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
import re
import time
import asyncio
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import get_container
from app.integrations.akshare.client import (
    IndustryBoard,
    LimitDownStock,
    LimitUpStock,
    StockQuote,
    get_industry_boards,
    get_limit_down_pool,
    get_limit_up_pool,
    get_stock_history_batch,
    get_stock_quote_by_symbols,
    peek_stock_quote_by_symbols,
    run_sync,
)
from app.models.researcher import Researcher as ResearcherModel
from app.models.trading import Position as PositionModel
from app.models.trading import TradingAccountSnapshot as SnapshotModel
from app.models.trading import TradeLog as TradeLogModel
from app.models.trading import TradeRecord as RecordModel
from app.models.trading import TradingAccount as AccountModel
from app.modules.trading.quote_cache import get_cached_quotes, get_or_refresh_cached_quotes, refresh_cached_quotes
from app.modules.trading.reflection_skill import TradingReflectionSkill
from app.modules.trading.paper_trading_engine import (
    ORDER_STATUS_FILLED,
    MarketSnapshot,
    compute_sellable_quantity,
    execute_stock_order,
)
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
    TradeLogSection,
    TradeRecord,
    TradingAccount,
    TradingAllData,
    TradingPortfolioData,
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
_reflection_skill = TradingReflectionSkill()


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


@dataclass
class _DailyAccountSnapshot:
    trade_date: date
    total_asset: float
    available_cash: float
    holding_value: float
    daily_pnl: float


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
    def _sort_positions(items: list[PositionItem]) -> list[PositionItem]:
        return sorted(items, key=lambda item: (abs(item.pnl), item.pnl, item.symbol), reverse=True)

    @staticmethod
    def _infer_initial_capital(account: AccountModel | object | None) -> float:
        """统一返回模拟盘初始资金口径。"""
        return DEFAULT_INITIAL_CAPITAL

    @staticmethod
    def _derive_recent_pnl(
        *,
        total_asset: float,
        initial_capital: float,
        replay: _ReplaySnapshot | object | None,
    ) -> float:
        """Derive recent PnL from the account equity curve for ranking views."""
        daily_equity = getattr(replay, "daily_equity", None)
        if isinstance(daily_equity, dict) and daily_equity:
            today_str = datetime.now().date().strftime("%Y-%m-%d")
            previous_dates = [date_text for date_text in daily_equity if str(date_text) < today_str]
            if previous_dates:
                base_equity = float(daily_equity[max(previous_dates)])
                return round(total_asset - base_equity, 2)
            return round(total_asset - initial_capital, 2)
        return round(total_asset - initial_capital, 2)

    def _account_to_schema(
        self,
        acc: AccountModel | object,
        *,
        replay: _ReplaySnapshot | None = None,
    ) -> TradingAccount:
        initial_capital = self._infer_initial_capital(acc)
        total_asset = round(float(getattr(acc, "total_asset", initial_capital)), 2)
        total_pnl = round(total_asset - initial_capital, 2)
        return TradingAccount(
            account_id=str(getattr(acc, "id")),
            initial_capital=initial_capital,
            total_asset=total_asset,
            available_cash=round(float(getattr(acc, "available_cash", 0.0)), 2),
            holding_value=round(float(getattr(acc, "holding_value", 0.0)), 2),
            daily_pnl=round(float(getattr(acc, "daily_pnl", 0.0)), 2),
            total_pnl=total_pnl,
            total_return=round(total_pnl / initial_capital, 4) if initial_capital > 0 else 0.0,
        )

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

    @staticmethod
    def _quote_snapshot_payload(quote: StockQuote | None) -> dict[str, object] | None:
        if quote is None:
            return None
        return {
            "symbol": quote.symbol,
            "name": quote.name,
            "price": float(quote.price),
            "change": float(quote.change),
            "change_pct": float(quote.change_pct),
            "open": float(quote.open),
            "high": float(quote.high),
            "low": float(quote.low),
            "prev_close": float(quote.prev_close),
            "volume": float(quote.volume),
            "amount": float(quote.amount),
            "turnover_ratio": float(getattr(quote, "turnover_ratio", 0.0) or 0.0),
            "volume_ratio": float(getattr(quote, "volume_ratio", 0.0) or 0.0),
            "industry": str(getattr(quote, "industry", "") or ""),
            "main_net_inflow": float(getattr(quote, "main_net_inflow", 0.0) or 0.0),
            "main_net_inflow_pct": float(getattr(quote, "main_net_inflow_pct", 0.0) or 0.0),
            "timestamp": quote.timestamp,
        }

    @staticmethod
    def _industry_snapshot_payload(board: IndustryBoard | None) -> dict[str, object] | None:
        if board is None:
            return None
        return {
            "name": board.name,
            "change_pct": float(board.change_pct),
            "total_volume": float(board.total_volume),
            "total_amount": float(board.total_amount),
            "net_inflow": float(board.net_inflow),
            "rise_count": int(board.rise_count),
            "fall_count": int(board.fall_count),
            "leading_stock": board.leading_stock,
            "leading_stock_pct": float(board.leading_stock_pct),
        }

    @staticmethod
    def _limit_stock_payload(item: LimitUpStock | LimitDownStock | None) -> dict[str, object] | None:
        if item is None:
            return None
        payload: dict[str, object] = {
            "symbol": item.symbol,
            "name": item.name,
            "change_pct": float(item.change_pct),
            "price": float(item.price),
            "amount": float(item.amount),
            "turnover_ratio": float(item.turnover_ratio),
        }
        if isinstance(item, LimitUpStock):
            payload.update(
                {
                    "seal_amount": float(item.seal_amount),
                    "first_seal_time": item.first_seal_time,
                    "last_seal_time": item.last_seal_time,
                    "break_count": int(item.break_count),
                    "consecutive": int(item.consecutive),
                    "industry": item.industry,
                }
            )
        return payload

    async def _build_trade_market_snapshot(
        self,
        symbol: str,
        quote: StockQuote | None = None,
    ) -> dict[str, object]:
        """为成交复盘收集真实行情、板块和情绪快照。"""
        snapshot_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        quote_payload = self._quote_snapshot_payload(quote)
        industry_name = str((quote_payload or {}).get("industry") or "")

        try:
            boards, limit_up_pool, limit_down_pool = await asyncio.gather(
                run_sync(get_industry_boards),
                run_sync(get_limit_up_pool),
                run_sync(get_limit_down_pool),
            )
        except Exception as exc:
            logger.warning("交易复盘行情快照获取失败: %s", exc)
            boards = []
            limit_up_pool = []
            limit_down_pool = []

        industry = next((item for item in boards if item.name == industry_name), None) if industry_name else None
        limit_up_item = next((item for item in limit_up_pool if item.symbol == symbol), None)
        limit_down_item = next((item for item in limit_down_pool if item.symbol == symbol), None)
        if industry is None and isinstance(limit_up_item, LimitUpStock) and limit_up_item.industry:
            industry = next((item for item in boards if item.name == limit_up_item.industry), None)
        industry_counter: Counter[str] = Counter(item.industry for item in limit_up_pool if item.industry)

        return {
            "snapshot_at": snapshot_time,
            "quote": quote_payload,
            "industry": self._industry_snapshot_payload(industry),
            "limit_up": self._limit_stock_payload(limit_up_item),
            "limit_down": self._limit_stock_payload(limit_down_item),
            "market_sentiment": {
                "snapshot_at": snapshot_time,
                "limit_up_count": len(limit_up_pool),
                "limit_down_count": len(limit_down_pool),
                "multi_board_count": sum(1 for item in limit_up_pool if item.consecutive >= 2),
                "highest_consecutive": max((item.consecutive for item in limit_up_pool), default=0),
                "top_limit_industries": [
                    {"industry": name, "limit_up_count": count}
                    for name, count in industry_counter.most_common(5)
                ],
            },
        }

    async def _load_realtime_quotes(
        self,
        symbols: list[str],
        *,
        cache_only: bool = False,
    ) -> dict[str, StockQuote]:
        """批量获取实时行情。

        - `cache_only=True`：只读本地缓存，不触发外部行情请求
        - `cache_only=False`：按 symbol 补齐缺失行情，适合下单等主动刷新场景
        """
        normalized_symbols = sorted({symbol for symbol in symbols if symbol})
        if not normalized_symbols:
            return {}
        try:
            redis = get_container().redis.get_client()
            if cache_only:
                return await get_cached_quotes(redis, normalized_symbols)
            return await get_or_refresh_cached_quotes(redis, normalized_symbols)
        except Exception:
            if cache_only:
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

    async def _load_account_snapshots(
        self,
        session: AsyncSession,
        account_id: str,
    ) -> list[SnapshotModel]:
        stmt = (
            select(SnapshotModel)
            .where(SnapshotModel.account_id == account_id)
            .order_by(SnapshotModel.trade_date.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def _upsert_account_snapshots(
        self,
        session: AsyncSession,
        account_id: str,
        snapshots: list[_DailyAccountSnapshot],
    ) -> None:
        if not snapshots:
            return

        existing_rows = await self._load_account_snapshots(session, account_id)
        existing_by_date = {row.trade_date: row for row in existing_rows}
        for snapshot in snapshots:
            existing = existing_by_date.get(snapshot.trade_date)
            if existing is None:
                session.add(
                    SnapshotModel(
                        id=f"tas_{uuid4().hex[:8]}",
                        account_id=account_id,
                        trade_date=snapshot.trade_date,
                        total_asset=snapshot.total_asset,
                        available_cash=snapshot.available_cash,
                        holding_value=snapshot.holding_value,
                        daily_pnl=snapshot.daily_pnl,
                    )
                )
            else:
                existing.total_asset = snapshot.total_asset
                existing.available_cash = snapshot.available_cash
                existing.holding_value = snapshot.holding_value
                existing.daily_pnl = snapshot.daily_pnl

    async def _load_account_records_in_range(
        self,
        session: AsyncSession,
        account_id: str,
        *,
        start_at: datetime,
        end_at: datetime,
    ) -> list[RecordModel]:
        """按时间范围查询成交记录。

        原始账户日内快照只关心当日成交，不应该每次都全量回放历史记录。
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

    async def _load_today_buy_quantities(
        self,
        session: AsyncSession,
        account_id: str,
    ) -> dict[str, int]:
        today = datetime.now().date()
        start_at = datetime.combine(today, datetime.min.time())
        end_at = start_at + timedelta(days=1)
        rows = await self._load_account_records_in_range(
            session,
            account_id,
            start_at=start_at,
            end_at=end_at,
        )
        quantities: dict[str, int] = defaultdict(int)
        for row in rows:
            if row.side == "buy":
                quantities[row.symbol] += int(row.quantity)
        return dict(quantities)

    async def _load_researcher_model(
        self,
        session: AsyncSession,
        researcher_id: str,
    ) -> ResearcherModel | None:
        stmt = select(ResearcherModel).where(ResearcherModel.id == researcher_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def async_resolve_account_model(
        self,
        session: AsyncSession,
        user_id: str,
        researcher_id: str,
    ) -> AccountModel:
        return await self._resolve_account_model(session, user_id, researcher_id)

    async def _append_trade_reflection_log(
        self,
        session: AsyncSession,
        *,
        account_id: str,
        researcher: ResearcherModel | None,
        trade_context: dict[str, object],
    ) -> None:
        """追加成交后的 AI 复盘日志，内容会覆盖交易复盘、执行反思与次日展望。"""
        # 把 session 和 account_id 塞进 trade_context,让 reflection_skill
        # 能拉取当日其他成交 / 该股历史成交,生成上下文敏感的复盘
        enriched_ctx = dict(trade_context)
        enriched_ctx.setdefault("session", session)
        enriched_ctx.setdefault("account_id", account_id)
        reflection = await _reflection_skill.build_trade_reflection(
            researcher_name=researcher.name if researcher else "小市值研究员",
            researcher_prompt=researcher.prompt if researcher else "",
            trade_context=enriched_ctx,
        )
        session.add(
            TradeLogModel(
                id=f"tl_{uuid4().hex[:8]}",
                account_id=account_id,
                log_type="analysis",
                trade_record_ids="[]",
                title=_reflection_skill.build_trade_log_title(trade_context),
                content=reflection,
            )
        )

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
                # 注:TradeRecord.commission 字段在新撮合下已经包含 transfer_fee
                # (撮合时存的是 commission + transfer_fee 之和),所以 cost_price
                # 仍然是 fully-loaded 的。
                cash -= amount + commission
                cost_price = round((amount + commission) / quantity, 4)
                lots[symbol].append(_Lot(quantity=quantity, unit_cost=cost_price, bought_at=dt))
                market_price[symbol] = price
            else:
                # 卖出端:重新算一遍印花税和过户费(因为 TradeRecord.commission
                # 字段是 commission+transfer_fee,没有单独存 tax)。
                from app.modules.trading.account_state import AccountStateManager

                stamp_tax = AccountStateManager.calc_stamp_tax(amount)
                cash += amount - commission - stamp_tax
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
                    # 容错:出现超卖数据时,避免把收益算成异常高值
                    estimated_cost = price * remaining
                    cost_basis += estimated_cost
                    consumed += remaining

                if symbol_lots:
                    market_price[symbol] = price
                else:
                    market_price.pop(symbol, None)

                cost_price = round(cost_basis / quantity, 4) if quantity > 0 else None
                # 关键修复:realized_pnl 必须扣印花税,否则虚增 1‰ * amount
                realized_pnl = round(amount - commission - stamp_tax - cost_basis, 2)
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
                position_ratio=round(amount / initial_capital, 4) if initial_capital > 0 else None,
                created_at=dt,
            )

        return _ReplaySnapshot(
            record_map=record_map,
            daily_equity=daily_equity,
            sell_pnls=sell_pnls,
            hold_days=hold_days,
        )

    async def _build_snapshots_from_market_history(
        self,
        records: list[RecordModel],
        *,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ) -> list[_DailyAccountSnapshot]:
        """按历史日 K 收盘价回放账户每日权益。"""
        if not records:
            return []

        start_date = min(row.created_at.date() for row in records)
        end_date = max(row.created_at.date() for row in records)
        symbols = sorted({row.symbol for row in records if row.symbol})
        history_map = await run_sync(
            get_stock_history_batch,
            symbols,
            start_date,
            end_date,
        )
        price_by_symbol_date: dict[str, dict[date, float]] = {}
        all_market_dates: set[date] = set()
        for symbol, bars in history_map.items():
            price_by_date: dict[date, float] = {}
            for bar in bars:
                try:
                    bar_date = datetime.strptime(bar.date, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if start_date <= bar_date <= end_date and bar.close > 0:
                    price_by_date[bar_date] = float(bar.close)
                    all_market_dates.add(bar_date)
            price_by_symbol_date[symbol] = price_by_date

        if not all_market_dates:
            return []

        records_by_date: dict[date, list[RecordModel]] = defaultdict(list)
        for row in records:
            records_by_date[row.created_at.date()].append(row)

        cash = float(initial_capital)
        lots: dict[str, deque[_Lot]] = defaultdict(deque)
        latest_price: dict[str, float] = {}
        previous_total = initial_capital
        snapshots: list[_DailyAccountSnapshot] = []

        for trade_date in sorted(all_market_dates):
            for row in records_by_date.get(trade_date, []):
                price = float(row.price)
                quantity = int(row.quantity)
                commission = float(getattr(row, "commission", 0.0) or 0.0)
                amount = round(price * quantity, 2)
                if row.side == "buy":
                    cash -= amount + commission
                    unit_cost = round((amount + commission) / quantity, 4) if quantity > 0 else price
                    lots[row.symbol].append(_Lot(quantity=quantity, unit_cost=unit_cost, bought_at=row.created_at))
                else:
                    # 卖出现金净额扣印花税(与 _replay_records 一致)
                    from app.modules.trading.account_state import AccountStateManager
                    stamp_tax = AccountStateManager.calc_stamp_tax(amount)
                    cash += amount - commission - stamp_tax
                    remaining = quantity
                    symbol_lots = lots[row.symbol]
                    while remaining > 0 and symbol_lots:
                        lot = symbol_lots[0]
                        take = min(remaining, lot.quantity)
                        lot.quantity -= take
                        remaining -= take
                        if lot.quantity == 0:
                            symbol_lots.popleft()
                latest_price[row.symbol] = price

            holding_value = 0.0
            for symbol, symbol_lots in lots.items():
                quantity = sum(lot.quantity for lot in symbol_lots)
                if quantity <= 0:
                    continue
                market_price = price_by_symbol_date.get(symbol, {}).get(trade_date)
                if market_price is not None:
                    latest_price[symbol] = market_price
                price = latest_price.get(symbol)
                if price is None:
                    continue
                holding_value += quantity * price

            total_asset = round(cash + holding_value, 2)
            daily_pnl = round(total_asset - previous_total, 2)
            snapshots.append(
                _DailyAccountSnapshot(
                    trade_date=trade_date,
                    total_asset=total_asset,
                    available_cash=round(cash, 2),
                    holding_value=round(holding_value, 2),
                    daily_pnl=daily_pnl,
                )
            )
            previous_total = total_asset

        return snapshots

    async def _get_or_build_account_snapshots(
        self,
        session: AsyncSession,
        account_id: str,
        records: list[RecordModel],
        *,
        initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    ) -> list[SnapshotModel]:
        existing = await self._load_account_snapshots(session, account_id)
        if records:
            latest_record_date = max(row.created_at.date() for row in records)
            latest_snapshot_date = max((row.trade_date for row in existing), default=None)
            if latest_snapshot_date is None or latest_snapshot_date < latest_record_date:
                generated = await self._build_snapshots_from_market_history(
                    records,
                    initial_capital=initial_capital,
                )
                await self._upsert_account_snapshots(session, account_id, generated)
                await session.flush()
                existing = await self._load_account_snapshots(session, account_id)
        return existing

    async def _refresh_account_snapshot(
        self,
        session: AsyncSession,
        account: AccountModel,
        *,
        cache_only: bool = True,
    ) -> None:
        """根据最新行情重算账户全部字段(holding_value / total_asset / daily_pnl)。

        统一走 AccountStateManager,确保撮合时、定时盯市、API 调用三处口径一致:
          - holding_value = Σ(latest_price * qty),不再用近似累加
          - total_asset   = available_cash + holding_value
          - daily_pnl     = realized_today + floating_today
        """
        from app.modules.trading.account_state import AccountStateManager

        repo = PositionRepository(session)
        positions = await repo.list_by_account(account.id)
        quote_map = await self._load_realtime_quotes(
            [position.symbol for position in positions],
            cache_only=cache_only,
        )

        # 1) 盯市:更新 position.current_price/pnl + account.holding_value/total_asset
        _, floating_daily_pnl = AccountStateManager.mark_to_market(
            account, positions, quote_map,
        )

        # 2) 重算 realized_today(优先走 replay 的精确值)
        today = datetime.now().date()
        start_at = datetime.combine(today, datetime.min.time())
        end_at = start_at + timedelta(days=1)
        today_records = await self._load_account_records_in_range(
            session, account.id, start_at=start_at, end_at=end_at,
        )

        realized_daily_pnl = 0.0
        if today_records:
            if any(row.side == "sell" for row in today_records):
                # 当日有卖出:用 replay 还原 fully-loaded 成本价计算精确 realized
                records = await self._load_account_records(session, account.id)
                replay = self._replay_records(records)
                for record in replay.record_map.values():
                    if record.created_at.date() != today:
                        continue
                    if record.side == "buy":
                        # 买入端的"费用"算 realized 负贡献(commission + transfer_fee)
                        realized_daily_pnl -= float(record.commission or 0.0)
                    elif record.realized_pnl is not None:
                        realized_daily_pnl += record.realized_pnl
            else:
                # 当日仅有买入:realized = -Σ(费用)
                realized_daily_pnl = -sum(
                    float(row.commission or 0.0) for row in today_records
                )

        account.daily_pnl = round(realized_daily_pnl + floating_daily_pnl, 2)

    async def async_get_account(
        self, session: AsyncSession, user_id: str, researcher_id: str
    ) -> TradingAccount:
        """从数据库查询模拟账户快照。"""
        cache_key = f"account:{user_id}:{researcher_id}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, TradingAccount):
            return cached

        acc = await self._resolve_account_model(session, user_id, researcher_id)
        _, replay = await self._load_replay(session, acc.id)

        data = self._account_to_schema(acc, replay=replay)
        self._cache_set(cache_key, data, ACCOUNT_CACHE_TTL_SECONDS)
        return data

    async def async_list_positions(
        self,
        session: AsyncSession,
        account_id: str,
        *,
        cache_only: bool = True,
        include_sellable_quantity: bool = False,
    ) -> list[PositionItem]:
        """从数据库查询持仓快照。

        详情页和工作台只需要展示持仓盈亏，不需要每次都查当天买入数量。
        `include_sellable_quantity=True` 仅留给确实要展示 T+1 可卖数量的场景。
        """
        if cache_only:
            cache_key = f"positions:{account_id}:{int(include_sellable_quantity)}"
            cached = self._cache_get(cache_key)
            if isinstance(cached, list):
                return cached

        repo = PositionRepository(session)
        positions = await repo.list_by_account(account_id)
        today_buy_quantities = (
            await self._load_today_buy_quantities(session, account_id)
            if include_sellable_quantity
            else {}
        )
        items = [
            PositionItem(
                symbol=position.symbol,
                name=position.name,
                quantity=position.quantity,
                sellable_quantity=(
                    compute_sellable_quantity(
                        int(position.quantity),
                        today_buy_quantities.get(position.symbol, 0),
                    )
                    if include_sellable_quantity
                    else None
                ),
                cost_price=float(position.cost_price),
                current_price=float(position.current_price),
                pnl=float(position.pnl),
            )
            for position in positions
        ]
        sorted_items = self._sort_positions(items)
        if cache_only:
            self._cache_set(
                f"positions:{account_id}:{int(include_sellable_quantity)}",
                sorted_items,
                POSITIONS_CACHE_TTL_SECONDS,
            )
        return sorted_items

    async def _load_replay(
        self, session: AsyncSession, account_id: str,
    ) -> tuple[list[RecordModel], _ReplaySnapshot]:
        """加载成交记录并回放（可复用，避免多个方法各自重复加载）。"""
        cache_key = f"replay:{account_id}"
        cached = self._cache_get(cache_key)
        if isinstance(cached, tuple) and len(cached) == 2:
            return cached  # type: ignore[return-value]

        records = await self._load_account_records(session, account_id)
        replay = self._replay_records(records)
        self._cache_set(cache_key, (records, replay), ACCOUNT_CACHE_TTL_SECONDS)
        return records, replay

    async def async_list_records(
        self, session: AsyncSession, account_id: str, *, limit: int = 20,
        _replay: tuple[list[RecordModel], _ReplaySnapshot] | None = None,
    ) -> list[TradeRecord]:
        """从数据库查询成交记录，并补齐成本/已实现盈亏等增强字段。"""
        records, replay = _replay or await self._load_replay(session, account_id)
        desc_items = [replay.record_map[row.id] for row in reversed(records)]
        return desc_items[:limit]

    async def async_list_logs(
        self, session: AsyncSession, account_id: str, *, limit: int = 100,
        _replay: tuple[list[RecordModel], _ReplaySnapshot] | None = None,
    ) -> list[TradeLogItem]:
        """从数据库查询交易日志（trade + analysis 条目），并填充增强后的成交记录。"""
        stmt = (
            select(TradeLogModel)
            .where(TradeLogModel.account_id == account_id)
            .order_by(TradeLogModel.created_at.desc(), TradeLogModel.id.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        logs = list(result.scalars().all())

        _, replay = _replay or await self._load_replay(session, account_id)

        items: list[TradeLogItem] = []
        for log in logs:
            try:
                record_ids = json.loads(log.trade_record_ids or "[]")
            except Exception:
                record_ids = []
            related_records = [replay.record_map[record_id] for record_id in record_ids if record_id in replay.record_map]
            content = self._normalize_analysis_content(log.log_type, log.content or "")
            items.append(
                TradeLogItem(
                    log_id=log.id,
                    log_type=log.log_type,
                    trade_records=related_records,
                    title=log.title or "",
                    content=content,
                    sections=self._extract_analysis_sections(log.log_type, content),
                    created_at=log.created_at,
                )
            )
        return items

    async def async_generate_reflection_for_latest_trade(
        self,
        session: AsyncSession,
        *,
        account: AccountModel,
        researcher: ResearcherModel | None,
    ) -> TradeLogItem:
        """基于最近一条真实成交记录调用 LLM 生成 AI 复盘并落库。"""
        records, replay = await self._load_replay(session, account.id)
        if not records:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="暂无成交记录可复盘")

        latest_row = records[-1]
        latest_record = replay.record_map.get(latest_row.id)
        if latest_record is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="最近成交记录不可用")

        trade_context = {
            "mode": "manual_reflection",
            "side": latest_record.side,
            "symbol": latest_record.symbol,
            "name": latest_record.name,
            "price": latest_record.price,
            "quantity": latest_record.quantity,
            "amount": latest_record.amount,
            "commission": latest_record.commission,
            "reason": "基于最近一笔真实成交日志补生成复盘",
            "cost_price": latest_record.cost_price,
            "realized_pnl": latest_record.realized_pnl,
            "realized_pnl_pct": latest_record.realized_pnl_pct,
            "position_ratio": latest_record.position_ratio,
            "total_asset": float(account.total_asset),
            "available_cash": float(account.available_cash),
        }
        quote_map = await self._load_realtime_quotes([latest_record.symbol], cache_only=False)
        trade_context["market_snapshot"] = await self._build_trade_market_snapshot(
            latest_record.symbol,
            quote_map.get(latest_record.symbol),
        )
        # 注入 session / account_id 让 reflection_skill 能拉上下文
        trade_context["session"] = session
        trade_context["account_id"] = account.id
        try:
            reflection = await _reflection_skill.build_trade_reflection(
                researcher_name=researcher.name if researcher else "交易研究员",
                researcher_prompt=researcher.prompt if researcher else "",
                trade_context=trade_context,
                allow_fallback=False,
            )
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"AI 复盘生成失败：{exc}",
            ) from exc
        content = self._normalize_analysis_content("analysis", reflection)
        log = TradeLogModel(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="analysis",
            trade_record_ids="[]",
            title=_reflection_skill.build_trade_log_title(trade_context),
            content=content,
        )
        session.add(log)
        await session.commit()
        self._cache_invalidate([f"replay:{account.id}"])
        return TradeLogItem(
            log_id=log.id,
            log_type=log.log_type,
            trade_records=[],
            title=log.title or "",
            content=content,
            sections=self._extract_analysis_sections("analysis", content),
            created_at=log.created_at,
        )

    async def async_snapshot_account(
        self,
        session: AsyncSession,
        account: AccountModel,
        *,
        trade_date: date | None = None,
    ) -> _DailyAccountSnapshot:
        """刷新账户当前行情并持久化当天账户快照。"""
        snapshot_date = trade_date or datetime.now().date()
        await self._refresh_account_snapshot(session, account, cache_only=False)
        existing = await self._load_account_snapshots(session, account.id)
        previous_rows = [row for row in existing if row.trade_date < snapshot_date]
        previous_total = (
            float(max(previous_rows, key=lambda row: row.trade_date).total_asset)
            if previous_rows
            else DEFAULT_INITIAL_CAPITAL
        )
        snapshot = _DailyAccountSnapshot(
            trade_date=snapshot_date,
            total_asset=round(float(account.total_asset), 2),
            available_cash=round(float(account.available_cash), 2),
            holding_value=round(float(account.holding_value), 2),
            daily_pnl=round(float(account.total_asset) - previous_total, 2),
        )
        await self._upsert_account_snapshots(session, account.id, [snapshot])
        self._cache_invalidate([f"stats:{account.id}", f"account:", f"positions:{account.id}"])
        return snapshot

    @staticmethod
    def _fill_weekday_equity(daily_equity: dict[str, float]) -> dict[str, float]:
        """补齐交易区间内工作日权益；无成交日沿用上一交易日权益。"""
        if not daily_equity:
            return {}

        parsed_dates = [datetime.strptime(day, "%Y-%m-%d").date() for day in daily_equity]
        start_date = min(parsed_dates)
        end_date = max(parsed_dates)
        filled: dict[str, float] = {}
        previous_equity: float | None = None
        cursor = start_date
        while cursor <= end_date:
            if cursor.weekday() < 5:
                key = cursor.strftime("%Y-%m-%d")
                if key in daily_equity:
                    previous_equity = daily_equity[key]
                if previous_equity is not None:
                    filled[key] = previous_equity
            cursor += timedelta(days=1)
        return filled

    @staticmethod
    def _normalize_analysis_content(log_type: str, content: str) -> str:
        """把旧交易分析日志补成统一的 AI 复盘阅读结构。"""
        text = content.strip()
        if log_type != "analysis" or not text:
            return content
        required_sections = ("交易复盘", "执行反思", "次日展望")
        if all(section in text for section in required_sections):
            return text
        return (
            "## 交易复盘\n"
            f"{text}\n\n"
            "## 执行反思\n"
            "本次操作已按既定策略规则完成。后续需要重点复核成交价格、仓位暴露与调仓节奏，避免因单一信号导致组合过度集中。\n\n"
            "## 次日展望\n"
            "下一交易日优先观察持仓标的开盘强弱、板块延续性和风险事件变化。若价格偏离策略预期，应按模拟盘规则继续执行止盈止损与轮动纪律。"
        )

    @staticmethod
    def _extract_analysis_sections(log_type: str, content: str) -> list[TradeLogSection]:
        """从 Markdown 复盘中提取工作台需要的三段结构化内容。"""
        if log_type != "analysis":
            return []

        section_defs = [
            ("trade_review", "交易复盘"),
            ("execution_reflection", "执行反思"),
            ("next_day_outlook", "次日展望"),
        ]
        lines = content.strip().splitlines()
        sections: dict[str, list[str]] = {key: [] for key, _ in section_defs}
        title_to_key = {title: key for key, title in section_defs}
        current_key: str | None = None

        for line in lines:
            stripped = line.strip()
            heading_match = re.match(r"^##\s+(.+?)\s*$", stripped)
            if heading_match:
                heading = heading_match.group(1).strip()
                current_key = title_to_key.get(heading)
                continue
            if current_key is not None:
                sections[current_key].append(line)

        return [
            TradeLogSection(
                key=key,
                title=title,
                content="\n".join(sections[key]).strip(),
            )
            for key, title in section_defs
            if "\n".join(sections[key]).strip()
        ]

    async def async_get_all(
        self,
        session: AsyncSession,
        user_id: str,
        researcher_id: str,
    ) -> TradingAllData:
        """一次请求返回模拟盘全部页面数据。

        核心优化：只加载一次成交记录、只回放一次，然后复用到
        account / positions / records / logs 各视图。
        """
        acc = await self._resolve_account_model(session, user_id, researcher_id)
        account_id = acc.id

        # 1. 持仓与账户总览直接读取已落库快照。
        position_items = await self.async_list_positions(session, account_id, cache_only=True)

        # 2. 加载 & 回放成交记录（只做一次）
        replay_data = await self._load_replay(session, account_id)

        account_data = self._account_to_schema(acc, replay=replay_data[1])

        # 4. 成交记录（复用 replay）
        record_items = await self.async_list_records(
            session, account_id, limit=20, _replay=replay_data,
        )

        # 5. 交易日志（复用 replay）
        log_items = await self.async_list_logs(
            session, account_id, limit=200, _replay=replay_data,
        )

        return TradingAllData(
            account=account_data,
            positions=position_items,
            records=record_items,
            logs=log_items,
        )

    async def async_get_portfolio(
        self,
        session: AsyncSession,
        user_id: str,
        researcher_id: str,
    ) -> TradingPortfolioData:
        """返回工作台所需的轻量模拟盘数据，只包含账户和持仓。"""
        acc = await self._resolve_account_model(session, user_id, researcher_id)
        account_id = acc.id

        position_items = await self.async_list_positions(session, account_id, cache_only=True)
        _, replay = await self._load_replay(session, account_id)
        account_data = self._account_to_schema(acc, replay=replay)
        return TradingPortfolioData(account=account_data, positions=position_items)

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

        records, replay = await self._load_replay(session, account_id)
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

        snapshots = await self._get_or_build_account_snapshots(
            session,
            account_id,
            records,
            initial_capital=initial_capital,
        )
        daily_equity = {
            snapshot.trade_date.strftime("%Y-%m-%d"): round(float(snapshot.total_asset), 2)
            for snapshot in snapshots
        }

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
        - 原始账户日内盈亏扣除买入手续费

        卖出：
        - 检查持仓数量
        - 释放净资金（卖出金额 - 手续费 - 印花税）
        - 原始账户日内盈亏计入已实现盈亏
        """
        acct_repo = TradingAccountRepository(session)
        pos_repo = PositionRepository(session)
        researcher = await self._load_researcher_model(session, payload.researcher_id)

        # ── 行级锁：SELECT ... FOR UPDATE 防止并发下单竞态 ──
        acc = await acct_repo.get_by_user_researcher(user_id, payload.researcher_id)
        if not acc:
            acc = await acct_repo.get_by_researcher(payload.researcher_id)
        if not acc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模拟账户不存在")

        # 对账户加排他锁，确保同一账户的并发下单串行执行
        lock_stmt = (
            select(AccountModel)
            .where(AccountModel.id == acc.id)
            .with_for_update()
        )
        lock_result = await session.execute(lock_stmt)
        acc = lock_result.scalar_one()

        # 对持仓也加排他锁（如果存在），避免同一持仓并发修改
        existing = await pos_repo.get_by_account_symbol(acc.id, payload.symbol)
        if existing is not None:
            pos_lock_stmt = (
                select(PositionModel)
                .where(PositionModel.id == existing.id)
                .with_for_update()
            )
            pos_lock_result = await session.execute(pos_lock_stmt)
            existing = pos_lock_result.scalar_one_or_none()
        cost_price_before = float(existing.cost_price) if existing else None
        today_buy_quantities = await self._load_today_buy_quantities(session, acc.id)

        quote_map = await self._load_realtime_quotes([payload.symbol], cache_only=False)
        quote = quote_map.get(payload.symbol)
        resolved_name = (
            payload.name
            or (quote.name if quote else "")
            or (existing.name if existing else "")
            or payload.symbol
        )
        market = MarketSnapshot(
            price=float(quote.price) if quote else None,
            prev_close=float(quote.prev_close) if quote else None,
            volume=float(quote.volume) if quote else None,
        )
        sellable_quantity = None
        if payload.side == "sell":
            sellable_quantity = compute_sellable_quantity(
                int(existing.quantity) if existing else 0,
                today_buy_quantities.get(payload.symbol, 0),
            )

        execution = execute_stock_order(
            account=acc,
            existing_position=existing,
            symbol=payload.symbol,
            name=resolved_name,
            side=payload.side,
            quantity=payload.quantity,
            limit_price=payload.price,
            market=market,
            sellable_quantity=sellable_quantity,
            open_commission_rate=OPEN_COMMISSION_RATE,
            close_commission_rate=CLOSE_COMMISSION_RATE,
            close_tax_rate=CLOSE_TAX_RATE,
            min_commission=MIN_COMMISSION,
        )
        # 限价偏离市价 → 挂单(不报错)
        if execution.status == "ACTIVE":
            from app.modules.trading.pending_order_service import create_pending_order
            order = await create_pending_order(
                session,
                account_id=acc.id,
                symbol=payload.symbol,
                name=resolved_name,
                side=payload.side,
                quantity=payload.quantity,
                limit_price=payload.price,
            )
            await session.commit()
            return PlaceOrderResponse(
                trade_id=order.id,
                symbol=payload.symbol,
                side=payload.side,
                quantity=payload.quantity,
                filled_quantity=0,
                price=payload.price,
                amount=0.0,
                commission=0.0,
                tax=0.0,
                realized_pnl=None,
                status="ACTIVE",
                engine=execution.engine,
                message=f"挂单成功:等待行情匹配({execution.message})",
            )

        # 其他非 FILLED(REJECTED / CANCELLED)→ 报错
        if execution.status != ORDER_STATUS_FILLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=execution.message,
            )

        trade_id = f"trd_{uuid4().hex[:8]}"
        amount = round(execution.amount, 2)
        executed_price = round(float(execution.fill_price or payload.price), 4)
        total_fee = execution.total_fee
        realized_pnl = execution.realized_pnl if payload.side == "sell" else None
        reason = "用户在模拟盘中执行手动委托，需复盘本次决策与次日观察点"

        if payload.side == "buy":
            if existing is None and execution.created_position:
                session.add(
                    PositionModel(
                        id=f"pos_{uuid4().hex[:8]}",
                        account_id=acc.id,
                        symbol=payload.symbol,
                        name=resolved_name,
                        quantity=int(execution.created_position["quantity"]),
                        cost_price=float(execution.created_position["cost_price"]),
                        current_price=float(execution.created_position["current_price"]),
                        pnl=float(execution.created_position["pnl"]),
                    )
                )
                cost_price = float(execution.created_position["cost_price"])
            else:
                cost_price = float(existing.cost_price) if existing else None
        else:
            cost_price = cost_price_before
            if execution.remove_position and existing is not None:
                await session.delete(existing)

        realized_pnl_pct = (
            round(realized_pnl / (cost_price_before * payload.quantity), 4)
            if payload.side == "sell"
            and realized_pnl is not None
            and cost_price_before
            and payload.quantity > 0
            else None
        )

        session.add(
            RecordModel(
                id=trade_id,
                account_id=acc.id,
                symbol=payload.symbol,
                name=resolved_name,
                side=payload.side,
                quantity=execution.filled_quantity,
                price=executed_price,
                commission=total_fee,
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
        await session.flush()

        try:
            redis = get_container().redis.get_client()
            refreshed_quotes = await refresh_cached_quotes(redis, [payload.symbol])
            quote = refreshed_quotes.get(payload.symbol) or quote
        except Exception:
            pass

        await self._refresh_account_snapshot(session, acc)
        positions = await pos_repo.list_by_account(acc.id)
        market_snapshot = await self._build_trade_market_snapshot(payload.symbol, quote)
        await self._append_trade_reflection_log(
            session,
            account_id=acc.id,
            researcher=researcher,
            trade_context={
                "mode": "manual_order",
                "side": payload.side,
                "symbol": payload.symbol,
                "name": resolved_name,
                "price": executed_price,
                "quantity": execution.filled_quantity,
                "amount": amount,
                "commission": total_fee,
                "reason": reason,
                "cost_price": cost_price,
                "realized_pnl": realized_pnl,
                "realized_pnl_pct": realized_pnl_pct,
                "position_ratio": round(amount / DEFAULT_INITIAL_CAPITAL, 4) if DEFAULT_INITIAL_CAPITAL > 0 else 0.0,
                "total_asset": float(acc.total_asset),
                "available_cash": float(acc.available_cash),
                "holding_names": [position.name for position in positions],
                "market_snapshot": market_snapshot,
            },
        )
        await session.commit()
        self._cache_invalidate(
            [
                f"account:{user_id}:{payload.researcher_id}",
                f"positions:{acc.id}",
                f"replay:{acc.id}",
                f"stats:{acc.id}",
            ]
        )

        return PlaceOrderResponse(
            trade_id=trade_id,
            symbol=payload.symbol,
            side=payload.side,
            quantity=payload.quantity,
            filled_quantity=execution.filled_quantity,
            price=executed_price,
            amount=amount,
            commission=execution.commission,
            tax=execution.tax,
            realized_pnl=realized_pnl,
            status=execution.status,
            engine=execution.engine,
            message=execution.message,
        )
