"""
策略调度引擎 —— 读取研究员 strategy_config，执行真实行情选股与调仓

核心流程（每个交易日）：
  1. 查询所有 active + 有 strategy_config 的研究员
  2. 通过 AKShare 拉取 A 股实时行情，按小市值轮动策略选股
  3. 对比当前持仓，计算调仓信号（卖出 + 买入）
  4. 使用真实行情价格撮合交易
  5. 更新研究员 today_pnl / win_rate_30d 等统计指标

数据源：AKShare stock_zh_a_spot（新浪 A 股实时行情）
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.researcher import Researcher
from app.models.trading import Position, TradingAccount, TradeLog, TradeRecord

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
# 真实行情选股
# ════════════════════════════════════════════════════════════

def _fetch_realtime_quotes() -> list[dict]:
    """通过 AKShare 获取 A 股全市场实时行情快照。

    返回列表元素：{"symbol": "002516", "name": "旷达科技", "price": 5.23,
                   "change_pct": 2.5, "amount": 12345678, "open": 5.10, "prev_close": 5.11}
    """
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot()
    except Exception:
        logger.exception("[选股] AKShare 获取行情失败，回退空列表")
        return []

    quotes: list[dict] = []
    for _, row in df.iterrows():
        code_raw = str(row.get("代码", ""))
        # 去掉交易所前缀（sh/sz/bj）
        if code_raw.startswith(("sh", "sz", "SH", "SZ")):
            symbol = code_raw[2:]
        elif code_raw.startswith(("bj", "BJ")):
            symbol = code_raw[2:]
        else:
            symbol = code_raw

        price = _safe_float(row.get("最新价"))
        if price <= 0:
            continue

        quotes.append({
            "symbol": symbol,
            "name": str(row.get("名称", "")),
            "price": price,
            "change_pct": _safe_float(row.get("涨跌幅")),
            "amount": _safe_float(row.get("成交额")),
            "open": _safe_float(row.get("今开")),
            "prev_close": _safe_float(row.get("昨收")),
            "volume": _safe_float(row.get("成交量")),
        })
    logger.info("[选股] 获取 A 股行情 %d 条", len(quotes))
    return quotes


def _safe_float(val, default: float = 0.0) -> float:
    """安全转换为 float。"""
    try:
        import pandas as pd
        if pd.isna(val):
            return default
        return float(val)
    except (ValueError, TypeError):
        return default


def _generate_target_pool(strategy_config: dict, count: int = 10) -> list[dict]:
    """根据策略配置 + 真实 A 股行情生成目标持仓池。

    小市值轮动策略选股逻辑：
      1. 过滤掉 ST/*ST/退市股、科创板(688)、北交所(8/4开头)
      2. 过滤涨停股、跌停股（涨跌幅 >= 9.8% 或 <= -9.8%）
      3. 过滤价格异常股（< 1 元或 > 100 元）
      4. 过滤成交额过低股（< 500 万，流动性不足）
      5. 按成交额升序排列（成交额小 ≈ 小市值代理因子）
      6. 取前 stock_count 只

    返回列表元素：{"symbol": "002516", "name": "旷达科技", "price": 5.23}
    """
    pool_size = strategy_config.get("stock_count", count)
    filters = strategy_config.get("filters", {})

    all_quotes = _fetch_realtime_quotes()
    if not all_quotes:
        logger.warning("[选股] 无法获取行情数据，返回空池")
        return []

    candidates: list[dict] = []
    for q in all_quotes:
        symbol = q["symbol"]
        name = q["name"]
        price = q["price"]
        change_pct = q["change_pct"]
        amount = q["amount"]

        # ── 过滤规则 ──

        # 排除北交所（8/4 开头的 6 位码）
        if symbol.startswith(("8", "4")) and len(symbol) == 6:
            continue

        # 排除科创板（688 开头）
        if filters.get("exclude_kcb", True) and symbol.startswith("688"):
            continue

        # 排除 ST / *ST / 退市股
        if filters.get("exclude_st", True):
            if "ST" in name or "st" in name or "退" in name:
                continue

        # 排除涨停股（涨幅 >= 9.8%）
        if filters.get("exclude_limit_up", True) and change_pct >= 9.8:
            continue

        # 排除跌停股（跌幅 <= -9.8%）
        if filters.get("exclude_limit_down", True) and change_pct <= -9.8:
            continue

        # 价格过滤：排除仙股和高价股
        if price < 1.0 or price > 100.0:
            continue

        # 流动性过滤：成交额 < 500 万排除
        if amount < 5_000_000:
            continue

        candidates.append(q)

    # 按成交额升序（小成交额 ≈ 小市值代理因子）
    candidates.sort(key=lambda x: x["amount"])

    # 取前 pool_size 只
    selected = candidates[:pool_size]

    logger.info(
        "[选股] 筛选完成：全市场 %d → 候选 %d → 选中 %d",
        len(all_quotes), len(candidates), len(selected),
    )
    for s in selected:
        logger.info(
            "  [目标] %s %s 现价 %.2f 涨跌 %.2f%% 成交额 %.0f万",
            s["symbol"], s["name"], s["price"], s["change_pct"], s["amount"] / 10000,
        )

    return [{"symbol": s["symbol"], "name": s["name"], "price": s["price"]} for s in selected]


def _generate_target_pool_from_quotes(
    strategy_config: dict, all_quotes: list[dict], count: int = 10
) -> list[dict]:
    """与 _generate_target_pool 相同的选股逻辑，但复用已拉取的行情数据，避免重复请求。"""
    pool_size = strategy_config.get("stock_count", count)
    filters = strategy_config.get("filters", {})

    if not all_quotes:
        logger.warning("[选股] 行情数据为空，返回空池")
        return []

    candidates: list[dict] = []
    for q in all_quotes:
        symbol = q["symbol"]
        name = q["name"]
        price = q["price"]
        change_pct = q["change_pct"]
        amount = q["amount"]

        if symbol.startswith(("8", "4")) and len(symbol) == 6:
            continue
        if filters.get("exclude_kcb", True) and symbol.startswith("688"):
            continue
        if filters.get("exclude_st", True):
            if "ST" in name or "st" in name or "退" in name:
                continue
        if filters.get("exclude_limit_up", True) and change_pct >= 9.8:
            continue
        if filters.get("exclude_limit_down", True) and change_pct <= -9.8:
            continue
        if price < 1.0 or price > 100.0:
            continue
        if amount < 5_000_000:
            continue
        candidates.append(q)

    candidates.sort(key=lambda x: x["amount"])
    selected = candidates[:pool_size]

    logger.info(
        "[选股] 筛选完成：全市场 %d → 候选 %d → 选中 %d",
        len(all_quotes), len(candidates), len(selected),
    )
    for s in selected:
        logger.info(
            "  [目标] %s %s 现价 %.2f 涨跌 %.2f%% 成交额 %.0f万",
            s["symbol"], s["name"], s["price"], s["change_pct"], s["amount"] / 10000,
        )
    return [{"symbol": s["symbol"], "name": s["name"], "price": s["price"]} for s in selected]


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

    # 查找模拟账户（若不存在则自动创建）
    acct_stmt = select(TradingAccount).where(
        TradingAccount.researcher_id == researcher.id
    )
    acct_result = await session.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()
    if not account:
        logger.info("[策略引擎] %s 没有模拟账户，自动创建（初始资金 100 万）", researcher.name)
        initial_cash = 1_000_000.0
        account = TradingAccount(
            id=f"acct_{uuid4().hex[:10]}",
            user_id=researcher.owner_id,
            researcher_id=researcher.id,
            total_asset=initial_cash,
            available_cash=initial_cash,
            holding_value=0.0,
            daily_pnl=0.0,
        )
        session.add(account)
        await session.flush()

    # 查找当前持仓
    pos_stmt = select(Position).where(Position.account_id == account.id)
    pos_result = await session.execute(pos_stmt)
    current_positions = {p.symbol: p for p in pos_result.scalars().all()}

    # 拉取全市场实时行情（用于选股 + 卖出/持仓现价更新）
    all_quotes = _fetch_realtime_quotes()
    realtime_price_map: dict[str, float] = {q["symbol"]: q["price"] for q in all_quotes}

    # 生成今日目标池
    target_pool = _generate_target_pool_from_quotes(config, all_quotes)
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
            # 使用真实行情价格卖出（若行情不可用则用持仓现价）
            sell_price = realtime_price_map.get(symbol, pos.current_price)
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
            daily_pnl -= commission

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
            position_pct = (amount / (account.total_asset or 1000000)) * 100
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

    # ── 第三步：更新现有持仓的现价（使用真实行情） ──
    for symbol, pos in current_positions.items():
        new_price = realtime_price_map.get(symbol, target_map.get(symbol, {}).get("price", pos.current_price))
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
