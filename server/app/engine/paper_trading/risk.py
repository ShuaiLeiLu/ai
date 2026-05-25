from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.paper_trading.executor import do_sell, invalidate_trading_cache
from app.engine.paper_trading.state import get_limit_up_symbols
from app.engine.strategies.market import fetch_realtime_quotes
from app.integrations.akshare.client import run_sync
from app.integrations.openclaw.trade_push import (
    discard_strategy_trade_pushes,
    flush_strategy_trade_pushes,
)
from app.models.researcher import Researcher
from app.models.trading import Position, TradingAccount

logger = logging.getLogger(__name__)


async def _fetch_realtime_quotes_async() -> list[dict]:
    return await run_sync(fetch_realtime_quotes)


async def check_limit_up_open(session: AsyncSession) -> dict:
    """Generic 14:00 paper-trading risk check: sell tracked limit-up holdings after open."""
    stmt = select(Researcher).where(
        Researcher.status == "active",
        Researcher.strategy_config.isnot(None),
    )
    result = await session.execute(stmt)
    researchers = list(result.scalars().all())
    total_sold = 0
    affected: list[tuple[TradingAccount, str]] = []

    for researcher in researchers:
        rid = researcher.id
        limit_symbols = get_limit_up_symbols(rid)
        if not limit_symbols:
            continue

        config = researcher.strategy_config or {}
        cost_config = config.get("cost", {})
        close_commission_rate = cost_config.get("close_commission", 0.0003)
        close_tax_rate = cost_config.get("close_tax", 0.001)
        min_commission = cost_config.get("min_commission", 5)

        acct_stmt = select(TradingAccount).where(TradingAccount.researcher_id == rid)
        acct_result = await session.execute(acct_stmt)
        account = acct_result.scalar_one_or_none()
        if not account:
            continue

        realtime_map = {q["symbol"]: q for q in await _fetch_realtime_quotes_async()}
        pos_stmt = select(Position).where(Position.account_id == account.id)
        pos_result = await session.execute(pos_stmt)
        positions = {p.symbol: p for p in pos_result.scalars().all()}

        for sym in limit_symbols:
            pos = positions.get(sym)
            if not pos:
                continue
            q = realtime_map.get(sym)
            if not q:
                continue
            cur_price = q["price"]
            if q["change_pct"] < 9.8:
                logger.info("[涨停检查] %s(%s) 涨停打开，卖出", pos.name, sym)
                sold_count, _ = await do_sell(
                    session,
                    researcher,
                    account,
                    pos,
                    cur_price,
                    q,
                    close_commission_rate,
                    close_tax_rate,
                    min_commission,
                    "涨停打开，执行卖出",
                )
                total_sold += sold_count
                if sold_count > 0:
                    affected.append((account, researcher.id))
            else:
                logger.info("[涨停检查] %s(%s) 继续涨停，持有", pos.name, sym)

    if total_sold > 0:
        try:
            await session.commit()
        except Exception:
            discard_strategy_trade_pushes(session)
            raise
        for account, researcher_id in affected:
            invalidate_trading_cache(account, researcher_id)
        await flush_strategy_trade_pushes(session)

    return {"status": "ok", "sold_count": total_sold}
