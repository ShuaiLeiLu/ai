"""挂单池业务逻辑。

调用入口:
  - create_pending_order : 撮合返回 ACTIVE 时,把订单落到 pending_orders
  - list_pending_orders  : 给前端展示当前挂单
  - cancel_pending_order : 用户主动取消挂单
  - settle_pending_orders: 调度器每 30 秒扫描可成交挂单
  - expire_pending_orders: 15:05 自动把当日所有 ACTIVE 改成 EXPIRED
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.researcher import Researcher
from app.models.trading import (
    PendingOrder,
    Position,
    TradeLog,
    TradeRecord,
    TradingAccount,
)
from app.modules.trading.paper_trading_engine import (
    ORDER_STATUS_FILLED,
    MarketSnapshot,
    compute_sellable_quantity,
    execute_stock_order,
)

logger = logging.getLogger(__name__)

ORDER_STATUS_PENDING_ACTIVE = "ACTIVE"
ORDER_STATUS_PENDING_FILLED = "FILLED"
ORDER_STATUS_PENDING_CANCELLED = "CANCELLED"
ORDER_STATUS_PENDING_EXPIRED = "EXPIRED"


def _default_expires_at() -> datetime:
    """挂单默认有效期到当日 15:00(收盘)。

    若当前已过 15:00,则到次日 15:00(实际撮合循环会按交易日扫描)。
    """
    now = datetime.now(tz=UTC)
    # 上海时间 15:00 == UTC 07:00
    today_close = datetime.combine(now.date(), time(7, 0, 0)).replace(tzinfo=UTC)
    if now >= today_close:
        return today_close + timedelta(days=1)
    return today_close


async def create_pending_order(
    session: AsyncSession,
    *,
    account_id: str,
    symbol: str,
    name: str,
    side: str,
    quantity: int,
    limit_price: float,
) -> PendingOrder:
    order = PendingOrder(
        id=f"po_{uuid4().hex[:12]}",
        account_id=account_id,
        symbol=symbol,
        name=name or symbol,
        side=side,
        quantity=int(quantity),
        limit_price=float(limit_price),
        status=ORDER_STATUS_PENDING_ACTIVE,
        expires_at=_default_expires_at(),
    )
    session.add(order)
    await session.flush()
    return order


async def list_pending_orders(
    session: AsyncSession,
    *,
    account_id: str,
    statuses: list[str] | None = None,
    limit: int = 100,
) -> list[PendingOrder]:
    stmt = select(PendingOrder).where(PendingOrder.account_id == account_id)
    if statuses:
        stmt = stmt.where(PendingOrder.status.in_(statuses))
    stmt = stmt.order_by(PendingOrder.created_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def cancel_pending_order(
    session: AsyncSession,
    *,
    order_id: str,
    reason: str = "用户取消",
) -> PendingOrder | None:
    q = await session.execute(
        select(PendingOrder).where(
            PendingOrder.id == order_id,
            PendingOrder.status == ORDER_STATUS_PENDING_ACTIVE,
        )
    )
    order = q.scalar_one_or_none()
    if order is None:
        return None
    order.status = ORDER_STATUS_PENDING_CANCELLED
    order.cancel_reason = reason
    await session.flush()
    return order


async def expire_pending_orders(session: AsyncSession) -> int:
    """收盘后把所有未成交挂单改成 EXPIRED。"""
    now = datetime.now(tz=UTC)
    q = await session.execute(
        select(PendingOrder).where(
            PendingOrder.status == ORDER_STATUS_PENDING_ACTIVE,
            PendingOrder.expires_at <= now,
        )
    )
    orders = list(q.scalars().all())
    for order in orders:
        order.status = ORDER_STATUS_PENDING_EXPIRED
        order.cancel_reason = "expired"
    if orders:
        await session.flush()
    return len(orders)


async def settle_pending_orders(session: AsyncSession) -> dict:
    """扫描所有 ACTIVE 挂单,按最新行情匹配可成交者并撮合。

    匹配规则:
      - 买单:limit_price >= 最新价 → 可成交,按最新价撮合
      - 卖单:limit_price <= 最新价 → 可成交
    成功:status=FILLED + filled_trade_id/price/at
    失败(资金/持仓不足等):status=CANCELLED + cancel_reason
    """
    from app.modules.trading.service import TradingService

    q = await session.execute(
        select(PendingOrder).where(PendingOrder.status == ORDER_STATUS_PENDING_ACTIVE)
    )
    active_orders = list(q.scalars().all())
    if not active_orders:
        return {"checked": 0, "filled": 0, "skipped": 0}

    # 聚合所有标的的行情,一次性拉
    symbols = sorted({o.symbol for o in active_orders})
    service = TradingService()
    quote_map = await service._load_realtime_quotes(symbols, cache_only=False)

    filled_count = 0
    skipped_count = 0
    for order in active_orders:
        # 过期先丢弃
        now = datetime.now(tz=UTC)
        if order.expires_at <= now:
            order.status = ORDER_STATUS_PENDING_EXPIRED
            order.cancel_reason = "expired"
            continue

        quote = quote_map.get(order.symbol)
        if quote is None or float(quote.price) <= 0:
            skipped_count += 1
            continue

        market_price = float(quote.price)
        # 限价单匹配
        if order.side == "buy":
            if order.limit_price < market_price:
                skipped_count += 1
                continue
        elif order.side == "sell":
            if order.limit_price > market_price:
                skipped_count += 1
                continue

        # 触发撮合(用挂单的限价)
        ok = await _execute_pending_order(session, order, quote, service)
        if ok:
            filled_count += 1
        else:
            skipped_count += 1

    return {
        "checked": len(active_orders),
        "filled": filled_count,
        "skipped": skipped_count,
    }


async def _execute_pending_order(
    session: AsyncSession,
    order: PendingOrder,
    quote,
    service,
) -> bool:
    """对一笔可成交挂单触发撮合。"""
    acc_q = await session.execute(
        select(TradingAccount).where(TradingAccount.id == order.account_id)
    )
    account = acc_q.scalar_one_or_none()
    if account is None:
        order.status = ORDER_STATUS_PENDING_CANCELLED
        order.cancel_reason = "账户已删除"
        return False

    # 查 existing position(卖单必需 / 买单加仓时用)
    pos_q = await session.execute(
        select(Position).where(
            Position.account_id == account.id,
            Position.symbol == order.symbol,
        ).with_for_update()
    )
    existing = pos_q.scalar_one_or_none()

    # 卖单还要校验 T+1 sellable
    sellable_quantity = None
    if order.side == "sell":
        today_buy_q = await session.execute(
            select(TradeRecord).where(
                TradeRecord.account_id == account.id,
                TradeRecord.symbol == order.symbol,
                TradeRecord.side == "buy",
                TradeRecord.created_at
                >= datetime.combine(datetime.now().date(), time.min),
            )
        )
        today_bought = sum(int(r.quantity) for r in today_buy_q.scalars().all())
        sellable_quantity = compute_sellable_quantity(
            int(existing.quantity) if existing else 0, today_bought,
        )

    market = MarketSnapshot(
        price=float(quote.price),
        prev_close=float(getattr(quote, "prev_close", 0.0) or 0.0) or None,
        volume=float(getattr(quote, "volume", 0.0) or 0.0) or None,
    )
    execution = execute_stock_order(
        account=account,
        existing_position=existing,
        symbol=order.symbol,
        name=order.name,
        side=order.side,
        quantity=int(order.quantity),
        limit_price=float(order.limit_price),
        market=market,
        sellable_quantity=sellable_quantity,
    )
    if execution.status != ORDER_STATUS_FILLED:
        order.status = ORDER_STATUS_PENDING_CANCELLED
        order.cancel_reason = execution.message or "撮合未通过"
        return False

    # 落 TradeRecord
    trade_id = f"trd_{uuid4().hex[:8]}"
    session.add(
        TradeRecord(
            id=trade_id,
            account_id=account.id,
            symbol=order.symbol,
            name=order.name,
            side=order.side,
            quantity=execution.filled_quantity,
            price=round(float(execution.fill_price or order.limit_price), 4),
            commission=execution.total_fee,
        )
    )
    # 落 TradeLog
    session.add(
        TradeLog(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="trade",
            trade_record_ids=json.dumps([trade_id]),
            title=f"挂单成交｜{order.name}({order.symbol})",
            content="",
        )
    )

    # 买入新建持仓
    if order.side == "buy" and existing is None and execution.created_position:
        session.add(
            Position(
                id=f"pos_{uuid4().hex[:8]}",
                account_id=account.id,
                symbol=order.symbol,
                name=order.name,
                quantity=int(execution.created_position["quantity"]),
                cost_price=float(execution.created_position["cost_price"]),
                current_price=float(execution.created_position["current_price"]),
                pnl=float(execution.created_position["pnl"]),
            )
        )
    # 卖空持仓时删除
    if (
        order.side == "sell"
        and execution.remove_position
        and existing is not None
    ):
        await session.delete(existing)

    # 回填挂单状态
    order.status = ORDER_STATUS_PENDING_FILLED
    order.filled_trade_id = trade_id
    order.filled_price = round(float(execution.fill_price or order.limit_price), 4)
    order.filled_at = datetime.now(tz=UTC)

    await session.flush()
    # 撮合后即时盯市
    await service._refresh_account_snapshot(session, account, cache_only=True)
    return True
