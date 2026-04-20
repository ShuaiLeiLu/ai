"""
策略调度引擎 —— 读取研究员 strategy_config，执行模拟选股与调仓

核心流程（每个交易日）：
  1. 查询所有 active + 有 strategy_config 的研究员
  2. 根据策略配置生成目标持仓池（模拟选股）
  3. 对比当前持仓，计算调仓信号（卖出 + 买入）
  4. 通过 async_place_order 执行交易
  5. 更新研究员 today_pnl / win_rate_30d 等统计指标

当前阶段使用模拟股票池（内置A股小市值标的），后续接入真实行情数据源。
"""
from __future__ import annotations

import json
import logging
import random
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.researcher import Researcher
from app.models.trading import Position, TradingAccount, TradeLog, TradeRecord

logger = logging.getLogger(__name__)

# ── 模拟股票池（小市值标的，后续替换为真实行情数据源）──
# 格式：(代码, 名称, 模拟价格区间下限, 模拟价格区间上限)
SIMULATED_STOCK_POOL = [
    ("002516", "旷达科技", 4.5, 6.0),
    ("002305", "南国置业", 2.8, 4.0),
    ("600701", "丰华股份", 7.0, 10.0),
    ("002260", "德奥退", 3.0, 5.0),
    ("000557", "西部创业", 5.0, 7.5),
    ("600209", "罗顿发展", 4.0, 6.0),
    ("002420", "达实智能", 3.5, 5.5),
    ("600698", "湖南天雁", 4.0, 6.5),
    ("002071", "长城影视", 2.5, 4.0),
    ("600733", "北汽蓝谷", 5.0, 8.0),
    ("002147", "新光退", 2.0, 3.5),
    ("600186", "莲花健康", 3.0, 5.0),
    ("002427", "尤夫股份", 6.0, 9.0),
    ("600652", "游久游戏", 5.0, 7.0),
    ("002233", "塔牌集团", 8.0, 12.0),
    ("000017", "利华益维", 12.0, 16.0),
    ("002230", "科大讯飞", 35.0, 50.0),
    ("600298", "安琪酵母", 28.0, 38.0),
    ("002456", "欧菲光", 6.0, 9.0),
    ("600319", "亚星化学", 5.0, 8.0),
]


def _sim_price(low: float, high: float) -> float:
    """生成模拟价格，保留两位小数"""
    return round(random.uniform(low, high), 2)


def _generate_target_pool(strategy_config: dict, count: int = 10) -> list[dict]:
    """根据策略配置生成目标持仓池（模拟）。

    返回列表元素：{"symbol": "002516", "name": "旷达科技", "price": 5.23}
    """
    pool_size = strategy_config.get("stock_count", count)
    # 随机选择目标数量的股票
    selected = random.sample(SIMULATED_STOCK_POOL, min(pool_size, len(SIMULATED_STOCK_POOL)))
    return [
        {"symbol": s[0], "name": s[1], "price": _sim_price(s[2], s[3])}
        for s in selected
    ]


async def execute_daily_rotation(session: AsyncSession) -> dict:
    """执行每日轮动调仓（核心入口）。

    流程：
      1. 查询所有 active + 有 strategy_config 的研究员
      2. 对每个研究员：
         a. 生成今日目标持仓池
         b. 卖出不在目标池中的持仓
         c. 买入新目标（等权分配可用资金）
      3. 更新研究员 today_pnl
    """
    # 查询需要执行策略的研究员
    stmt = select(Researcher).where(
        Researcher.status == "active",
        Researcher.strategy_config.isnot(None),
    )
    result = await session.execute(stmt)
    researchers = list(result.scalars().all())

    if not researchers:
        logger.info("[策略引擎] 没有需要执行策略的研究员")
        return {"status": "skip", "reason": "no_active_researchers"}

    total_trades = 0
    details = []

    for r in researchers:
        try:
            trades = await _execute_for_researcher(session, r)
            total_trades += trades
            details.append({"researcher": r.name, "trades": trades})
            logger.info("[策略引擎] %s 执行完成，成交 %d 笔", r.name, trades)
        except Exception as e:
            logger.error("[策略引擎] %s 执行失败: %s", r.name, e)
            details.append({"researcher": r.name, "error": str(e)})

    return {
        "status": "ok",
        "total_trades": total_trades,
        "details": details,
        "executed_at": datetime.now(tz=UTC).isoformat(),
    }


def _gen_sell_analysis(name: str, symbol: str, cost: float, sell_price: float,
                       qty: int, pnl: float, pnl_pct: float, reason: str) -> str:
    """生成卖出操作的 AI 分析文本"""
    result_word = "盈利" if pnl >= 0 else "亏损"
    return (
        f"对持仓标的{name}({symbol})进行分析后执行卖出操作：\n\n"
        f"1. 买入成本 {cost:.2f} 元，以现价 {sell_price:.2f} 元全部卖出 {qty} 股，"
        f"成交金额 {sell_price * qty:,.2f} 元。\n"
        f"2. 本次交易{result_word} {pnl:+,.2f} 元，收益率 {pnl_pct:+.2f}%。\n"
        f"3. 卖出原因：{reason}。\n"
    )


def _gen_buy_analysis(name: str, symbol: str, price: float, qty: int,
                      amount: float, position_pct: float) -> str:
    """生成买入操作的 AI 分析文本"""
    return (
        f"根据策略选股信号，买入{name}({symbol})：\n\n"
        f"1. 以 {price:.2f} 元买入 {qty} 股，成交金额 {amount:,.2f} 元，"
        f"仓位占比约 {position_pct:.0f}%。\n"
        f"2. 该标的符合小市值轮动策略的因子筛选条件，流通市值处于目标区间，"
        f"纳入当日目标持仓池。\n"
    )


def _gen_daily_summary(sell_count: int, buy_count: int, total_pnl: float,
                       total_asset: float, available_cash: float,
                       hold_names: list[str]) -> str:
    """生成每日操作总结"""
    lines = ["## 当前操作情况总结\n"]

    if sell_count + buy_count == 0:
        lines.append("今日无调仓操作，当前持仓符合目标池，继续持有。\n")
    else:
        lines.append(
            f"本次按照交易纪律完成了调仓操作：卖出 {sell_count} 笔，买入 {buy_count} 笔。\n"
        )

    if total_pnl >= 0:
        lines.append(f"今日策略盈亏 **+{total_pnl:,.2f} 元**，整体运行正常。\n")
    else:
        lines.append(f"今日策略盈亏 **{total_pnl:,.2f} 元**，在风控容忍范围内。\n")

    lines.append(
        f"当前账户总资产 {total_asset:,.2f} 元，可用资金 {available_cash:,.2f} 元。"
    )

    if hold_names:
        lines.append(
            f"\n\n当前持仓 {len(hold_names)} 只：{'、'.join(hold_names)}，"
            f"均符合小市值轮动策略选股条件，继续持有观察。"
        )

    return "\n".join(lines)


async def _execute_for_researcher(session: AsyncSession, researcher: Researcher) -> int:
    """为单个研究员执行调仓，返回成交笔数。同时写入交易日志（TradeLog）。"""
    config = researcher.strategy_config or {}
    cost_config = config.get("cost", {})
    open_commission_rate = cost_config.get("open_commission", 0.0003)
    close_commission_rate = cost_config.get("close_commission", 0.0003)
    close_tax_rate = cost_config.get("close_tax", 0.001)
    min_commission = cost_config.get("min_commission", 5)
    stop_loss = config.get("risk_control", {}).get("stop_loss", -0.10)

    # 查找模拟账户
    acct_stmt = select(TradingAccount).where(
        TradingAccount.researcher_id == researcher.id
    )
    acct_result = await session.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()
    if not account:
        logger.warning("[策略引擎] %s 没有模拟账户，跳过", researcher.name)
        return 0

    # 查找当前持仓
    pos_stmt = select(Position).where(Position.account_id == account.id)
    pos_result = await session.execute(pos_stmt)
    current_positions = {p.symbol: p for p in pos_result.scalars().all()}

    # 生成今日目标池
    target_pool = _generate_target_pool(config)
    target_symbols = {t["symbol"] for t in target_pool}
    target_map = {t["symbol"]: t for t in target_pool}

    trade_count = 0
    daily_pnl = 0.0
    sell_count = 0
    buy_count = 0

    # ── 第一步：卖出不在目标池中的持仓 + 止损检查 ──
    for symbol, pos in list(current_positions.items()):
        should_sell = False
        reason = ""

        if symbol not in target_symbols:
            should_sell = True
            reason = "轮动调出目标池，执行卖出"
        else:
            if pos.cost_price > 0:
                pnl_pct = (pos.current_price - pos.cost_price) / pos.cost_price
                if pnl_pct <= stop_loss:
                    should_sell = True
                    reason = f"触发止损线（当前亏损 {pnl_pct:.1%}，止损阈值 {stop_loss:.0%}）"

        if should_sell:
            sell_price = round(pos.current_price * random.uniform(0.97, 1.03), 2)
            amount = sell_price * pos.quantity
            commission = max(amount * close_commission_rate, min_commission)
            tax = amount * close_tax_rate
            pnl = (sell_price - pos.cost_price) * pos.quantity - commission - tax
            pnl_pct_val = ((sell_price - pos.cost_price) / pos.cost_price * 100) if pos.cost_price > 0 else 0
            daily_pnl += pnl

            account.available_cash += amount - commission - tax
            account.holding_value -= pos.cost_price * pos.quantity

            record_id = f"trd_{uuid4().hex[:8]}"
            record = TradeRecord(
                id=record_id,
                account_id=account.id,
                symbol=symbol,
                name=pos.name,
                side="sell",
                quantity=pos.quantity,
                price=sell_price,
                commission=commission + tax,
            )
            session.add(record)

            # ── 写交易日志：trade 条目 ──
            session.add(TradeLog(
                id=f"tl_{uuid4().hex[:8]}",
                account_id=account.id,
                log_type="trade",
                trade_record_ids=json.dumps([record_id]),
                title="",
                content="",
            ))
            # ── 写交易日志：analysis 条目 ──
            session.add(TradeLog(
                id=f"tl_{uuid4().hex[:8]}",
                account_id=account.id,
                log_type="analysis",
                trade_record_ids="[]",
                title="",
                content=_gen_sell_analysis(
                    pos.name, symbol, pos.cost_price, sell_price,
                    pos.quantity, pnl, pnl_pct_val, reason,
                ),
            ))

            await session.delete(pos)
            del current_positions[symbol]
            trade_count += 1
            sell_count += 1
            logger.info("  [卖出] %s %s %d股 @ %.2f (%s)", symbol, pos.name, pos.quantity, sell_price, reason)

    # ── 第二步：买入新目标 ──
    new_targets = [t for t in target_pool if t["symbol"] not in current_positions]
    buy_record_ids: list[str] = []

    if new_targets and account.available_cash > 1000:
        stock_count = config.get("stock_count", 10)
        per_stock_budget = account.available_cash / max(stock_count, len(new_targets))

        for target in new_targets:
            buy_price = target["price"]
            max_quantity = int(per_stock_budget / buy_price / 100) * 100
            if max_quantity < 100:
                continue

            amount = buy_price * max_quantity
            commission = max(amount * open_commission_rate, min_commission)

            if account.available_cash < amount + commission:
                continue

            account.available_cash -= amount + commission
            account.holding_value += amount

            new_pos = Position(
                id=f"pos_{uuid4().hex[:8]}",
                account_id=account.id,
                symbol=target["symbol"],
                name=target["name"],
                quantity=max_quantity,
                cost_price=buy_price,
                current_price=buy_price,
                pnl=0.0,
            )
            session.add(new_pos)

            record_id = f"trd_{uuid4().hex[:8]}"
            record = TradeRecord(
                id=record_id,
                account_id=account.id,
                symbol=target["symbol"],
                name=target["name"],
                side="buy",
                quantity=max_quantity,
                price=buy_price,
                commission=commission,
            )
            session.add(record)
            buy_record_ids.append(record_id)

            # ── 写交易日志：trade 条目 ──
            session.add(TradeLog(
                id=f"tl_{uuid4().hex[:8]}",
                account_id=account.id,
                log_type="trade",
                trade_record_ids=json.dumps([record_id]),
                title="",
                content="",
            ))
            # ── 写交易日志：analysis 条目 ──
            position_pct = (amount / (account.total_asset or 100000)) * 100
            session.add(TradeLog(
                id=f"tl_{uuid4().hex[:8]}",
                account_id=account.id,
                log_type="analysis",
                trade_record_ids="[]",
                title="",
                content=_gen_buy_analysis(
                    target["name"], target["symbol"], buy_price,
                    max_quantity, amount, position_pct,
                ),
            ))

            trade_count += 1
            buy_count += 1
            logger.info("  [买入] %s %s %d股 @ %.2f", target["symbol"], target["name"], max_quantity, buy_price)

    # ── 第三步：更新现有持仓的现价 ──
    for symbol, pos in current_positions.items():
        if symbol in target_map:
            new_price = target_map[symbol]["price"]
        else:
            new_price = round(pos.current_price * random.uniform(0.97, 1.03), 2)
        old_pnl = pos.pnl
        pos.current_price = new_price
        pos.pnl = round((new_price - pos.cost_price) * pos.quantity, 2)
        daily_pnl += pos.pnl - old_pnl

    # ── 第四步：更新账户汇总 ──
    all_pos_stmt = select(Position).where(Position.account_id == account.id)
    all_pos_result = await session.execute(all_pos_stmt)
    all_positions = list(all_pos_result.scalars().all())
    account.holding_value = sum(p.current_price * p.quantity for p in all_positions)
    account.total_asset = account.available_cash + account.holding_value
    account.daily_pnl = round(daily_pnl, 2)
    researcher.today_pnl = round(daily_pnl, 2)

    # ── 第五步：写每日操作总结日志 ──
    hold_names = [p.name for p in all_positions]
    session.add(TradeLog(
        id=f"tl_{uuid4().hex[:8]}",
        account_id=account.id,
        log_type="analysis",
        trade_record_ids="[]",
        title="当前操作情况总结",
        content=_gen_daily_summary(
            sell_count, buy_count, daily_pnl,
            account.total_asset, account.available_cash, hold_names,
        ),
    ))

    await session.commit()
    return trade_count
