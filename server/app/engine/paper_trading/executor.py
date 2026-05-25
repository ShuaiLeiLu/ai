from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.openclaw.trade_push import queue_strategy_trade_push
from app.models.researcher import Researcher
from app.models.trading import Position, TradeLog, TradeRecord, TradingAccount
from app.modules.trading.paper_trading_engine import (
    ORDER_STATUS_FILLED,
    MarketSnapshot,
    compute_sellable_quantity,
    execute_stock_order,
)
from app.modules.trading.reflection_skill import TradingReflectionSkill

logger = logging.getLogger(__name__)
_trading_reflection_skill = TradingReflectionSkill()


async def build_trade_market_snapshot(symbol: str, market_quote: dict | None = None) -> dict:
    from app.modules.trading.service import TradingService

    service = TradingService()
    quote_map = await service._load_realtime_quotes([symbol], cache_only=False)
    quote = quote_map.get(symbol)
    return await service._build_trade_market_snapshot(symbol, quote)


def invalidate_trading_cache(account: TradingAccount, researcher_id: str) -> None:
    from app.modules.trading.service import TradingService

    TradingService._cache_invalidate(
        [
            f"account:{account.user_id}:{researcher_id}",
            f"positions:{account.id}",
            f"replay:{account.id}",
            f"stats:{account.id}",
        ]
    )


async def load_today_buy_quantities(session: AsyncSession, account_id: str) -> dict[str, int]:
    today = datetime.now().date()
    start_at = datetime.combine(today, datetime.min.time())
    end_at = start_at + timedelta(days=1)
    stmt = (
        select(TradeRecord)
        .where(
            TradeRecord.account_id == account_id,
            TradeRecord.side == "buy",
            TradeRecord.created_at >= start_at,
            TradeRecord.created_at < end_at,
        )
        .order_by(TradeRecord.created_at.asc(), TradeRecord.id.asc())
    )
    result = await session.execute(stmt)
    quantities: dict[str, int] = defaultdict(int)
    for record in result.scalars().all():
        quantities[record.symbol] += int(record.quantity)
    return dict(quantities)


async def do_sell(
    session: AsyncSession,
    researcher: Researcher,
    account: TradingAccount,
    pos: Position,
    sell_price: float,
    market_quote: dict | None,
    comm_rate: float,
    tax_rate: float,
    min_comm: float,
    reason: str,
    quantity: int | None = None,
) -> tuple[int, float]:
    """Execute a paper sell order and return (trade_count, realized_pnl)."""
    today_buy_quantities = await load_today_buy_quantities(session, account.id)
    order_quantity = int(quantity or pos.quantity)
    sellable_quantity = compute_sellable_quantity(
        int(pos.quantity),
        today_buy_quantities.get(pos.symbol, 0),
    )
    execution = execute_stock_order(
        account=account,
        existing_position=pos,
        symbol=pos.symbol,
        name=pos.name,
        side="sell",
        quantity=order_quantity,
        limit_price=float(sell_price),
        market=MarketSnapshot(
            price=float(sell_price),
            prev_close=float(market_quote.get("prev_close", 0.0)) if market_quote else None,
            volume=float(market_quote.get("volume", 0.0)) if market_quote else None,
        ),
        sellable_quantity=sellable_quantity,
        open_commission_rate=comm_rate,
        close_commission_rate=comm_rate,
        close_tax_rate=tax_rate,
        min_commission=min_comm,
    )
    if execution.status != ORDER_STATUS_FILLED:
        logger.warning("  [卖出跳过] %s %s: %s", pos.symbol, pos.name, execution.message)
        return 0, 0.0

    amount = round(execution.amount, 2)
    fill_price = round(float(execution.fill_price or sell_price), 4)
    total_fee = execution.total_fee
    pnl = round(float(execution.realized_pnl or 0.0), 2)

    record = TradeRecord(
        id=f"trd_{uuid4().hex[:8]}",
        account_id=account.id,
        symbol=pos.symbol,
        name=pos.name,
        side="sell",
        quantity=execution.filled_quantity,
        price=fill_price,
        commission=total_fee,
    )
    session.add(record)
    session.add(
        TradeLog(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="trade",
            trade_record_ids=json.dumps([record.id]),
            title="",
            content="",
        )
    )
    strategy_config = researcher.strategy_config or {}
    market_snapshot = await build_trade_market_snapshot(pos.symbol, market_quote)
    reflection = await _trading_reflection_skill.build_trade_reflection(
        researcher_name=researcher.name,
        researcher_prompt=researcher.prompt,
        trade_context={
            "mode": "strategy",
            "strategy_type": strategy_config.get("strategy_type", "smallcap_rotation"),
            "side": "sell",
            "symbol": pos.symbol,
            "name": pos.name,
            "price": fill_price,
            "quantity": execution.filled_quantity,
            "amount": amount,
            "commission": total_fee,
            "reason": reason,
            "cost_price": float(pos.cost_price),
            "realized_pnl": round(pnl, 2),
            "realized_pnl_pct": round(pnl / (float(pos.cost_price) * execution.filled_quantity), 4)
            if pos.cost_price > 0 and execution.filled_quantity > 0
            else None,
            "position_ratio": round(amount / 1_000_000.0, 4),
            "available_cash": float(account.available_cash),
            "total_asset": float(account.available_cash + account.holding_value),
            "market_snapshot": market_snapshot,
            "session": session,
            "account_id": account.id,
        },
    )
    session.add(
        TradeLog(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="analysis",
            trade_record_ids="[]",
            title=_trading_reflection_skill.build_trade_log_title(
                {"side": "sell", "name": pos.name, "symbol": pos.symbol}
            ),
            content=reflection,
        )
    )

    if execution.remove_position:
        await session.delete(pos)

    await session.flush()
    # 撮合完成后立即触发盯市,让 account.holding_value / total_asset / daily_pnl
    # 即时反映本笔成交后的状态
    from app.modules.trading.service import TradingService
    await TradingService()._refresh_account_snapshot(session, account, cache_only=True)
    queue_strategy_trade_push(
        session,
        researcher=researcher,
        account=account,
        record=record,
        amount=amount,
        reason=reason,
    )

    logger.info(
        "  [卖出] %s %s %d股 @ %.2f (%s)",
        pos.symbol,
        pos.name,
        execution.filled_quantity,
        fill_price,
        reason,
    )
    return 1, pnl


async def do_buy(
    session: AsyncSession,
    researcher: Researcher,
    account: TradingAccount,
    target: dict,
    budget: float,
    comm_rate: float,
    min_comm: float,
) -> tuple[int, float]:
    """Execute a paper buy order and return (trade_count, commission_pnl)."""
    buy_price = target["price"]
    max_quantity = int(budget / buy_price / 100) * 100
    if max_quantity < 100:
        return 0, 0.0

    execution = execute_stock_order(
        account=account,
        existing_position=None,
        symbol=target["symbol"],
        name=target["name"],
        side="buy",
        quantity=max_quantity,
        limit_price=float(buy_price),
        market=MarketSnapshot(
            price=float(target.get("price", buy_price)),
            prev_close=float(target.get("prev_close", 0.0)) or None,
            volume=float(target.get("volume", 0.0)) or None,
        ),
        sellable_quantity=None,
        open_commission_rate=comm_rate,
        close_commission_rate=comm_rate,
        close_tax_rate=0.001,
        min_commission=min_comm,
    )
    if execution.status != ORDER_STATUS_FILLED:
        logger.warning(
            "  [买入跳过] %s %s: %s",
            target["symbol"],
            target["name"],
            execution.message,
        )
        return 0, 0.0

    amount = round(execution.amount, 2)
    fill_price = round(float(execution.fill_price or buy_price), 4)
    if not execution.created_position:
        return 0, 0.0

    session.add(
        Position(
            id=f"pos_{uuid4().hex[:8]}",
            account_id=account.id,
            symbol=target["symbol"],
            name=target["name"],
            quantity=int(execution.created_position["quantity"]),
            cost_price=float(execution.created_position["cost_price"]),
            current_price=float(execution.created_position["current_price"]),
            pnl=float(execution.created_position["pnl"]),
        )
    )

    record = TradeRecord(
        id=f"trd_{uuid4().hex[:8]}",
        account_id=account.id,
        symbol=target["symbol"],
        name=target["name"],
        side="buy",
        quantity=execution.filled_quantity,
        price=fill_price,
        commission=execution.total_fee,
    )
    session.add(record)
    session.add(
        TradeLog(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="trade",
            trade_record_ids=json.dumps([record.id]),
            title="",
            content="",
        )
    )
    position_ratio = round(amount / 1_000_000.0, 4)
    strategy_config = researcher.strategy_config or {}
    market_snapshot = await build_trade_market_snapshot(target["symbol"], target)
    reflection = await _trading_reflection_skill.build_trade_reflection(
        researcher_name=researcher.name,
        researcher_prompt=researcher.prompt,
        trade_context={
            "mode": "strategy",
            "strategy_type": strategy_config.get("strategy_type", "smallcap_rotation"),
            "side": "buy",
            "symbol": target["symbol"],
            "name": target["name"],
            "price": fill_price,
            "quantity": execution.filled_quantity,
            "amount": amount,
            "commission": execution.total_fee,
            "reason": target.get("reason", "符合策略目标池，按交易纪律执行调入"),
            "position_ratio": position_ratio,
            "available_cash": float(account.available_cash),
            "total_asset": float(account.available_cash + account.holding_value),
            "market_snapshot": market_snapshot,
            "session": session,
            "account_id": account.id,
        },
    )
    session.add(
        TradeLog(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="analysis",
            trade_record_ids="[]",
            title=_trading_reflection_skill.build_trade_log_title(
                {"side": "buy", "name": target["name"], "symbol": target["symbol"]}
            ),
            content=reflection,
        )
    )

    await session.flush()
    # 撮合完成后立即触发盯市,让 account.holding_value / total_asset / daily_pnl
    # 即时反映本笔成交后的状态
    from app.modules.trading.service import TradingService
    await TradingService()._refresh_account_snapshot(session, account, cache_only=True)
    queue_strategy_trade_push(
        session,
        researcher=researcher,
        account=account,
        record=record,
        amount=amount,
        reason=str(target.get("reason", "符合策略目标池，按交易纪律执行调入")),
    )

    logger.info(
        "  [买入] %s %s %d股 @ %.2f",
        target["symbol"],
        target["name"],
        execution.filled_quantity,
        fill_price,
    )
    return 1, -execution.total_fee
