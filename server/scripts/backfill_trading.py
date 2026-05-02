"""
模拟盘数据补全脚本

因 CronTrigger 时区 bug，4/27~4/30 的策略调仓未在正确时间执行。
本脚本：
  1. 查询实际 A 股交易日
  2. 对小市值轮动 (c1eb2b)：用历史收盘价跑 4/28~4/30 止损检查
  3. 对超短情绪 (d73e0a)：检查 4/29 是否遗漏
  4. 用 4/30 收盘价更新全部持仓 current_price / pnl
  5. 从交易记录回放，修正两个账户的 available_cash / holding_value / total_asset
"""
from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("backfill")

DB_URL = "postgresql+asyncpg://sub2api:78e6363872039268b75fc4e1da5b2af5108f7f12530008d7@43.155.204.215:5432/cyber_invest"

# ── 需要补录的区间 ──
BACKFILL_START = date(2026, 4, 28)
BACKFILL_END = date(2026, 4, 30)

# ── 账户信息 ──
SMALLCAP_ACCT = "acct_a8b6c1eb2b"  # 小市值轮动
SMALLCAP_RESEARCHER = "r_b08dba104a"
SENTIMENT_ACCT = "acct_a7dbd73e0a"  # 超短情绪
SENTIMENT_RESEARCHER = "r_3452537f12"

INITIAL_CAPITAL = 1_000_000.0
STOP_LOSS_SMALLCAP = -0.10  # 小市值止损线
COMMISSION_RATE = 0.0003
TAX_RATE = 0.001
MIN_COMMISSION = 5.0


def _calc_commission(amount: float, rate: float) -> float:
    return max(round(amount * rate, 2), MIN_COMMISSION)


def _calc_sell_fee(amount: float) -> float:
    comm = _calc_commission(amount, COMMISSION_RATE)
    tax = round(amount * TAX_RATE, 2)
    return comm + tax


def _fetch_hist_close(symbols: list[str], trade_date: date) -> dict[str, float]:
    """用 AKShare stock_zh_a_hist 批量取某天收盘价"""
    import akshare as ak
    result: dict[str, float] = {}
    dt_str = trade_date.strftime("%Y%m%d")
    for symbol in symbols:
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol, period="daily",
                start_date=dt_str, end_date=dt_str, adjust="qfq"
            )
            if df is not None and not df.empty:
                result[symbol] = float(df.iloc[0]["收盘"])
            else:
                log.warning("  [WARN] %s 在 %s 无历史数据", symbol, trade_date)
        except Exception as e:
            log.warning("  [WARN] %s 在 %s 获取失败: %s", symbol, trade_date, e)
    return result


async def _get_positions(session: AsyncSession, account_id: str) -> list[dict]:
    r = await session.execute(
        text("SELECT id, symbol, name, quantity, cost_price, current_price, pnl "
             "FROM positions WHERE account_id = :aid AND quantity > 0"),
        {"aid": account_id},
    )
    return [dict(zip(r.keys(), row)) for row in r.fetchall()]


async def _get_account(session: AsyncSession, account_id: str) -> dict:
    r = await session.execute(
        text("SELECT id, total_asset, available_cash, holding_value, daily_pnl "
             "FROM trading_accounts WHERE id = :aid"),
        {"aid": account_id},
    )
    row = r.fetchone()
    return dict(zip(r.keys(), row)) if row else {}


async def _insert_trade_record(session: AsyncSession, account_id: str,
                               symbol: str, name: str, side: str,
                               quantity: int, price: float, commission: float,
                               trade_date: date):
    rid = f"trd_{uuid4().hex[:8]}"
    ts = f"{trade_date.isoformat()} 09:31:00+00:00"
    await session.execute(
        text("INSERT INTO trade_records (id, account_id, symbol, name, side, quantity, price, commission, created_at, updated_at) "
             "VALUES (:id, :aid, :sym, :name, :side, :qty, :px, :comm, :ts, :ts)"),
        {"id": rid, "aid": account_id, "sym": symbol, "name": name,
         "side": side, "qty": quantity, "px": price, "comm": commission, "ts": ts},
    )
    # trade log
    tlid = f"tl_{uuid4().hex[:8]}"
    await session.execute(
        text("INSERT INTO trade_logs (id, account_id, log_type, trade_record_ids, title, content, created_at, updated_at) "
             "VALUES (:id, :aid, 'trade', :rids, :title, '', :ts, :ts)"),
        {"id": tlid, "aid": account_id, "rids": f'["{rid}"]',
         "title": f"{trade_date.isoformat()} 补录止损成交", "ts": ts},
    )
    return rid


async def run_backfill():
    engine = create_async_engine(DB_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ── Step 0: 确认交易日 ──
    log.info("=" * 60)
    log.info("Step 0: 确认交易日")
    import akshare as ak
    try:
        df = ak.stock_zh_a_hist(
            symbol="000001", period="daily",
            start_date=BACKFILL_START.strftime("%Y%m%d"),
            end_date=BACKFILL_END.strftime("%Y%m%d"),
            adjust="qfq",
        )
        if df is not None and not df.empty:
            import pandas as pd
            backfill_dates = [pd.to_datetime(d).date() for d in df["日期"].tolist()]
        else:
            raise ValueError("empty")
    except Exception:
        # fallback: 仅排除周末
        backfill_dates = [
            BACKFILL_START + timedelta(days=i)
            for i in range((BACKFILL_END - BACKFILL_START).days + 1)
            if (BACKFILL_START + timedelta(days=i)).weekday() < 5
        ]
    log.info("  补录区间 %s ~ %s, 实际交易日: %s", BACKFILL_START, BACKFILL_END, backfill_dates)

    if not backfill_dates:
        log.info("  无需补录的交易日，退出")
        await engine.dispose()
        return

    async with async_session() as session:
        # ── Step 1: 小市值轮动止损检查 ──
        log.info("=" * 60)
        log.info("Step 1: 小市值轮动 - 逐日止损检查 (%s)", SMALLCAP_ACCT)
        positions = await _get_positions(session, SMALLCAP_ACCT)
        log.info("  当前持仓 %d 只: %s", len(positions),
                 ", ".join(f"{p['symbol']} {p['name']}" for p in positions))

        sell_records = []
        for trade_date in backfill_dates:
            if not positions:
                break
            symbols = [p["symbol"] for p in positions]
            log.info("  --- %s 止损检查 ---", trade_date)
            closes = _fetch_hist_close(symbols, trade_date)

            remaining = []
            for pos in positions:
                sym = pos["symbol"]
                close = closes.get(sym)
                if close is None:
                    remaining.append(pos)
                    continue
                cost = float(pos["cost_price"])
                if cost <= 0:
                    remaining.append(pos)
                    continue
                pnl_pct = (close - cost) / cost
                if pnl_pct <= STOP_LOSS_SMALLCAP:
                    qty = int(pos["quantity"])
                    amount = close * qty
                    fee = _calc_sell_fee(amount)
                    log.info("    ★ 止损卖出 %s %s %d股 @ %.2f (亏损 %.1f%%)",
                             sym, pos["name"], qty, close, pnl_pct * 100)
                    await _insert_trade_record(
                        session, SMALLCAP_ACCT, sym, pos["name"],
                        "sell", qty, close, fee, trade_date)
                    # 标记 position quantity=0
                    await session.execute(
                        text("UPDATE positions SET quantity=0, current_price=:px, pnl=:pnl WHERE id=:pid"),
                        {"px": close, "pnl": round((close - cost) * qty, 2), "pid": pos["id"]})
                    sell_records.append({"symbol": sym, "name": pos["name"],
                                        "date": trade_date, "price": close, "qty": qty, "fee": fee})
                else:
                    log.info("    %s %s: close=%.2f, pnl=%.1f%% -> 持有",
                             sym, pos["name"], close, pnl_pct * 100)
                    remaining.append(pos)
            positions = remaining

        if not sell_records:
            log.info("  小市值轮动 4/28~4/30 无止损触发")
        else:
            log.info("  小市值轮动共止损 %d 笔", len(sell_records))

        # ── Step 2: 超短情绪检查 4/29 ──
        log.info("=" * 60)
        log.info("Step 2: 超短情绪 - 检查 4/29 是否遗漏 (%s)", SENTIMENT_ACCT)
        # 4/28 最后的交易: 卖紫光+兆易, 买韦尔+北方华创
        # 4/28 后持仓: 光迅科技 1300@134.52, 韦尔股份 1700@103.89, 北方华创 300@517.21
        # 4/30 交易: 卖光迅+韦尔, 买兆易+光迅
        # 所以 4/29 持仓不变 => 检查是否应有止损/止盈
        sentiment_pos_apr29 = [
            {"symbol": "002281", "name": "光迅科技", "qty": 1300, "cost": 134.52},
            {"symbol": "603501", "name": "韦尔股份", "qty": 1700, "cost": 103.89},
            {"symbol": "002371", "name": "北方华创", "qty": 300, "cost": 517.21},
        ]
        if date(2026, 4, 29) in backfill_dates:
            log.info("  4/29 是交易日，检查超短情绪持仓止损/止盈...")
            syms_29 = [p["symbol"] for p in sentiment_pos_apr29]
            closes_29 = _fetch_hist_close(syms_29, date(2026, 4, 29))
            stop_loss_short = -0.05
            take_profit_full = 0.15
            for p in sentiment_pos_apr29:
                close = closes_29.get(p["symbol"])
                if close is None:
                    log.info("    %s %s: 无数据", p["symbol"], p["name"])
                    continue
                pnl_pct = (close - p["cost"]) / p["cost"]
                action = "持有"
                if pnl_pct <= stop_loss_short:
                    action = "★ 应止损"
                elif pnl_pct >= take_profit_full:
                    action = "★ 应止盈"
                log.info("    %s %s: close=%.2f, pnl=%.1f%% -> %s",
                         p["symbol"], p["name"], close, pnl_pct * 100, action)
        else:
            log.info("  4/29 不是交易日，跳过")

        # ── Step 3: 用 4/30 收盘价更新所有持仓 ──
        log.info("=" * 60)
        log.info("Step 3: 用最近收盘价更新全部持仓")
        last_trade_date = backfill_dates[-1]
        for acct_id, acct_name in [(SMALLCAP_ACCT, "小市值轮动"), (SENTIMENT_ACCT, "超短情绪")]:
            pos_list = await _get_positions(session, acct_id)
            if not pos_list:
                log.info("  %s: 无持仓", acct_name)
                continue
            symbols = [p["symbol"] for p in pos_list]
            closes = _fetch_hist_close(symbols, last_trade_date)
            for p in pos_list:
                close = closes.get(p["symbol"])
                if close is None:
                    continue
                cost = float(p["cost_price"])
                qty = int(p["quantity"])
                new_pnl = round((close - cost) * qty, 2)
                log.info("  %s %s %s: %.2f -> %.2f, pnl=%.2f",
                         acct_name, p["symbol"], p["name"],
                         float(p["current_price"]), close, new_pnl)
                await session.execute(
                    text("UPDATE positions SET current_price=:px, pnl=:pnl WHERE id=:pid"),
                    {"px": close, "pnl": new_pnl, "pid": p["id"]})

        # ── Step 4: 从交易记录回放，修正账户余额 ──
        log.info("=" * 60)
        log.info("Step 4: 从交易记录回放修正账户余额")
        for acct_id, acct_name in [(SMALLCAP_ACCT, "小市值轮动"), (SENTIMENT_ACCT, "超短情绪")]:
            r = await session.execute(
                text("SELECT side, quantity, price, commission FROM trade_records "
                     "WHERE account_id = :aid ORDER BY created_at"),
                {"aid": acct_id})
            records = r.fetchall()
            cash = INITIAL_CAPITAL
            for rec in records:
                side, qty, price, comm = rec
                amount = float(price) * int(qty)
                if side == "buy":
                    cash -= (amount + float(comm))
                else:
                    cash += (amount - float(comm))

            # 计算持仓市值
            pos_list = await _get_positions(session, acct_id)
            holding_value = sum(float(p["current_price"]) * int(p["quantity"]) for p in pos_list)
            total_asset = round(cash + holding_value, 2)
            cash = round(cash, 2)
            holding_value = round(holding_value, 2)

            acct = await _get_account(session, acct_id)
            log.info("  %s 回放结果:", acct_name)
            log.info("    cash: %.2f -> %.2f", float(acct.get("available_cash", 0)), cash)
            log.info("    hold: %.2f -> %.2f", float(acct.get("holding_value", 0)), holding_value)
            log.info("    total: %.2f -> %.2f", float(acct.get("total_asset", 0)), total_asset)

            await session.execute(
                text("UPDATE trading_accounts SET available_cash=:cash, holding_value=:hold, "
                     "total_asset=:total, daily_pnl=0 WHERE id=:aid"),
                {"cash": cash, "hold": holding_value, "total": total_asset, "aid": acct_id})

        await session.commit()
        log.info("=" * 60)
        log.info("补全完成！已提交数据库。")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_backfill())
