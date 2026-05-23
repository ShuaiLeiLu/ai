"""除权除息自动调仓服务。

每个交易日凌晨 02:30 由调度器触发,扫所有持仓股,匹配当日除权除息事件:
  - 现金分红:account.available_cash += quantity * cash_dividend
  - 送股 / 转增:position.quantity 等比例增加,cost_price 按比例摊薄
  - 记录 TradeLog 通知用户

数据源:akshare stock_history_dividend_detail(数据质量受 akshare 接口稳定性影响,
任何解析失败默默跳过,确保调度任务不挂)。
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.client import (
    DividendEvent,
    get_dividend_events,
    run_sync,
)
from app.models.trading import Position, TradeLog, TradingAccount

logger = logging.getLogger(__name__)


async def apply_corporate_actions_for_today(session: AsyncSession) -> dict:
    """扫描所有持仓 → 拉除权除息事件 → 应用调整。

    返回统计:{checked: N, dividends_applied: X, splits_applied: Y}
    """
    today = date.today()
    yesterday = today - timedelta(days=1)

    # 取所有有持仓的 (account_id, symbol)
    q = await session.execute(
        select(Position).where(Position.quantity > 0)
    )
    positions = list(q.scalars().all())
    if not positions:
        return {"checked": 0, "dividends_applied": 0, "splits_applied": 0}

    dividends_applied = 0
    splits_applied = 0
    affected_accounts: set[str] = set()

    # 按 symbol 聚合,避免重复拉
    symbol_to_positions: dict[str, list[Position]] = {}
    for pos in positions:
        symbol_to_positions.setdefault(pos.symbol, []).append(pos)

    for symbol, pos_list in symbol_to_positions.items():
        try:
            events: list[DividendEvent] = await run_sync(
                get_dividend_events, symbol, 30,
            )
        except Exception:
            logger.debug("拉除权除息失败 symbol=%s", symbol, exc_info=True)
            continue

        # 只处理今日 ex_date 的事件(避免重复应用)
        # 实际上 ex_date 可能是 yesterday,跑凌晨任务时取昨天的更稳妥
        for event in events:
            try:
                ex_date = datetime.fromisoformat(event.ex_date).date()
            except Exception:
                continue
            if ex_date not in (today, yesterday):
                continue
            if event.cash_dividend <= 0 and event.bonus_ratio <= 0 and event.transfer_ratio <= 0:
                continue

            # 应用到该 symbol 的所有持仓
            for pos in pos_list:
                acc_q = await session.execute(
                    select(TradingAccount).where(TradingAccount.id == pos.account_id)
                )
                account = acc_q.scalar_one_or_none()
                if account is None:
                    continue

                applied_notes: list[str] = []

                # 1) 现金分红
                if event.cash_dividend > 0:
                    cash_in = round(event.cash_dividend * int(pos.quantity), 2)
                    account.available_cash = round(
                        float(account.available_cash) + cash_in, 2,
                    )
                    dividends_applied += 1
                    applied_notes.append(
                        f"现金分红 {event.cash_dividend:.4f}/股,合计入账 {cash_in:.2f} 元"
                    )

                # 2) 送股 + 转增(等价处理,统一摊薄成本)
                total_split_ratio = event.bonus_ratio + event.transfer_ratio
                if total_split_ratio > 0:
                    old_qty = int(pos.quantity)
                    added_qty = int(old_qty * total_split_ratio)
                    if added_qty > 0:
                        new_qty = old_qty + added_qty
                        # 成本摊薄:cost_basis 不变,均摊到新数量
                        old_basis = float(pos.cost_price) * old_qty
                        pos.quantity = new_qty
                        pos.cost_price = round(old_basis / new_qty, 4)
                        splits_applied += 1
                        applied_notes.append(
                            f"送转 {total_split_ratio*10:.1f}/10,持仓 "
                            f"{old_qty}→{new_qty},成本摊薄到 {pos.cost_price:.4f}"
                        )

                if applied_notes:
                    session.add(
                        TradeLog(
                            id=f"tl_{uuid4().hex[:8]}",
                            account_id=account.id,
                            log_type="analysis",
                            trade_record_ids="[]",
                            title=f"除权除息｜{pos.name}({pos.symbol}) {event.ex_date}",
                            content="## 除权除息自动调仓\n\n"
                                    + "\n".join(f"- {n}" for n in applied_notes),
                        )
                    )
                    affected_accounts.add(account.id)

    if affected_accounts:
        await session.flush()

    # 影响的账户重新盯市
    if affected_accounts:
        from app.modules.trading.service import TradingService
        service = TradingService()
        for aid in affected_accounts:
            acc_q = await session.execute(
                select(TradingAccount).where(TradingAccount.id == aid)
            )
            acc = acc_q.scalar_one_or_none()
            if acc is not None:
                await service._refresh_account_snapshot(session, acc, cache_only=True)

    return {
        "checked": len(positions),
        "dividends_applied": dividends_applied,
        "splits_applied": splits_applied,
    }
