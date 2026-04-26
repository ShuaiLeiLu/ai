from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.paper_trading.executor import do_buy, do_sell, invalidate_trading_cache
from app.engine.paper_trading.state import set_limit_up_symbols
from app.engine.strategies.market import fetch_realtime_quotes
from app.models.researcher import Researcher
from app.models.trading import Position, TradeLog, TradingAccount

logger = logging.getLogger(__name__)

STRATEGY_TYPE = "smallcap_rotation"
BLACKLIST_DAYS = 20

_hold_history: dict[str, list[list[str]]] = defaultdict(list)
_not_buy_again: dict[str, set[str]] = defaultdict(set)
_last_rotation_date: dict[str, str] = {}


def _filter_basic(all_quotes: list[dict], filters: dict) -> list[dict]:
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
            if "ST" in name or "st" in name or "退" in name or "*" in name:
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
    return candidates


def _pool_sg(candidates: list[dict], take: int = 5) -> list[dict]:
    pool = [q for q in candidates if q["pe_ratio"] > 0 and q["change_pct_ytd"] != 0]
    if not pool:
        return []

    pool.sort(key=lambda x: x["change_pct_ytd"], reverse=True)
    top10pct = pool[:max(1, len(pool) // 10)]
    top10pct.sort(key=lambda x: x.get("circulating_market_cap", 1e18))
    selected = top10pct[:take]
    logger.info("[SG池] 候选 %d → 前10%% %d → 选中 %d", len(pool), len(top10pct), len(selected))
    return selected


def _pool_ms(candidates: list[dict], take: int = 5) -> list[dict]:
    pool = [q for q in candidates if q["pe_ratio"] > 0]
    if not pool:
        return []

    df = pd.DataFrame(pool)
    df["rank_60d"] = df["change_pct_60d"].rank(pct=True, na_option="bottom")
    df["rank_ytd"] = df["change_pct_ytd"].rank(pct=True, na_option="bottom")
    df["rank_ep"] = (1.0 / df["pe_ratio"]).rank(pct=True, na_option="bottom")
    df["rank_vr"] = df["volume_ratio"].rank(pct=True, na_option="bottom")
    df["total_score"] = (
        0.35 * df["rank_60d"]
        + 0.40 * df["rank_ytd"]
        + 0.15 * df["rank_ep"]
        + 0.10 * df["rank_vr"]
    )

    df = df.sort_values("total_score", ascending=False)
    top10pct = df.head(max(1, len(df) // 10))
    top10pct = top10pct.sort_values("circulating_market_cap", ascending=True)

    selected_symbols = set(top10pct["symbol"].tolist()[:take])
    selected = [q for q in pool if q["symbol"] in selected_symbols]
    selected.sort(key=lambda x: x.get("circulating_market_cap", 1e18))
    selected = selected[:take]
    logger.info("[MS池] 候选 %d → 前10%% %d → 选中 %d", len(pool), len(top10pct), len(selected))
    return selected


def _pool_peg(candidates: list[dict], take: int = 5) -> list[dict]:
    pool = [q for q in candidates if q["pe_ratio"] > 0 and q["change_pct_ytd"] > 5]
    if not pool:
        return []

    for q in pool:
        q["_peg"] = q["pe_ratio"] / max(q["change_pct_ytd"], 1.0)

    pool.sort(key=lambda x: x["_peg"])
    top20pct = pool[:max(1, len(pool) // 5)]
    top20pct.sort(key=lambda x: x["turnover_ratio"])
    top50pct = top20pct[:max(1, len(top20pct) // 2)]
    top50pct.sort(key=lambda x: x.get("circulating_market_cap", 1e18))

    selected = top50pct[:take]
    logger.info(
        "[PEG池] 候选 %d → 前20%% %d → 低换手50%% %d → 选中 %d",
        len(pool),
        len(top20pct),
        len(top50pct),
        len(selected),
    )

    for q in pool:
        q.pop("_peg", None)
    return selected


def generate_target_pool_from_quotes(
    strategy_config: dict,
    all_quotes: list[dict],
    count: int = 10,
    blacklist: set[str] | None = None,
) -> list[dict]:
    pool_size = strategy_config.get("stock_count", count)
    filters = strategy_config.get("filters", {})
    blacklist = blacklist or set()

    if not all_quotes:
        logger.warning("[选股] 行情数据为空，返回空池")
        return []

    candidates = _filter_basic(all_quotes, filters)
    logger.info("[选股] 基础过滤：全市场 %d → 候选 %d", len(all_quotes), len(candidates))

    sg_list = _pool_sg(candidates, take=5)
    ms_list = _pool_ms(candidates, take=5)
    peg_list = _pool_peg(candidates, take=5)

    seen: set[str] = set()
    union_list: list[dict] = []
    for q in sg_list + ms_list + peg_list:
        if q["symbol"] not in seen:
            seen.add(q["symbol"])
            union_list.append(q)

    union_list.sort(key=lambda x: x.get("circulating_market_cap", 1e18))
    if blacklist:
        union_list = [q for q in union_list if q["symbol"] not in blacklist]

    selected = union_list[:pool_size]
    logger.info(
        "[选股] 三池并集 %d → 去黑名单后 %d → 最终选中 %d",
        len(seen),
        len(union_list),
        len(selected),
    )

    return [
        {
            "symbol": s["symbol"],
            "name": s["name"],
            "price": s["price"],
            "prev_close": s.get("prev_close", 0.0),
            "volume": s.get("volume", 0.0),
        }
        for s in selected
    ]


def generate_target_pool(strategy_config: dict, count: int = 10) -> list[dict]:
    return generate_target_pool_from_quotes(strategy_config, fetch_realtime_quotes(), count)


def _gen_daily_summary(
    sell_count: int,
    buy_count: int,
    total_pnl: float,
    total_asset: float,
    available_cash: float,
    hold_names: list[str],
) -> str:
    lines = ["## 当前操作情况总结\n"]
    if sell_count + buy_count == 0:
        lines.append("今日无调仓操作，当前持仓符合目标池，继续持有。\n")
    else:
        lines.append(
            f"本次按照交易纪律完成了调仓操作：卖出 {sell_count} 笔，"
            f"买入 {buy_count} 笔。\n"
        )

    if total_pnl >= 0:
        lines.append(f"今日策略盈亏 **+{total_pnl:,.2f} 元**，整体运行正常。\n")
    else:
        lines.append(f"今日策略盈亏 **{total_pnl:,.2f} 元**，在风控容忍范围内。\n")

    lines.append(f"当前账户总资产 {total_asset:,.2f} 元，可用资金 {available_cash:,.2f} 元。")
    if hold_names:
        lines.append(
            f"\n\n当前持仓 {len(hold_names)} 只：{'、'.join(hold_names)}，"
            f"均符合小市值轮动策略选股条件，继续持有观察。"
        )
    return "\n".join(lines)


async def execute(session: AsyncSession, researcher: Researcher) -> int:
    config = researcher.strategy_config or {}
    cost_config = config.get("cost", {})
    open_commission_rate = cost_config.get("open_commission", 0.0003)
    close_commission_rate = cost_config.get("close_commission", 0.0003)
    close_tax_rate = cost_config.get("close_tax", 0.001)
    min_commission = cost_config.get("min_commission", 5)
    stop_loss = config.get("risk_control", {}).get("stop_loss", -0.10)
    rid = researcher.id

    from zoneinfo import ZoneInfo

    now_shanghai = datetime.now(tz=ZoneInfo("Asia/Shanghai"))
    today_str = now_shanghai.strftime("%Y-%m-%d")
    is_monday = now_shanghai.weekday() == 0
    is_rotation_day = is_monday and _last_rotation_date.get(rid) != today_str

    acct_stmt = select(TradingAccount).where(TradingAccount.researcher_id == researcher.id)
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

    pos_stmt = select(Position).where(Position.account_id == account.id)
    pos_result = await session.execute(pos_stmt)
    current_positions = {p.symbol: p for p in pos_result.scalars().all()}
    hold_symbols = list(current_positions.keys())

    _hold_history[rid].append(hold_symbols)
    if len(_hold_history[rid]) > BLACKLIST_DAYS:
        _hold_history[rid] = _hold_history[rid][-BLACKLIST_DAYS:]
    temp_set: set[str] = set()
    for hl in _hold_history[rid]:
        temp_set.update(hl)
    _not_buy_again[rid] = temp_set

    all_quotes = fetch_realtime_quotes()
    realtime_quote_map: dict[str, dict] = {q["symbol"]: q for q in all_quotes}
    realtime_price_map: dict[str, float] = {q["symbol"]: q["price"] for q in all_quotes}
    realtime_change_map: dict[str, float] = {q["symbol"]: q["change_pct"] for q in all_quotes}

    high_limit_list = [sym for sym in hold_symbols if realtime_change_map.get(sym, 0) >= 9.8]
    set_limit_up_symbols(rid, high_limit_list)
    if high_limit_list:
        logger.info("[策略引擎] %s 涨停持仓: %s", researcher.name, high_limit_list)

    trade_count = 0
    daily_pnl = 0.0
    sell_count = 0
    buy_count = 0

    if is_rotation_day:
        logger.info("[策略引擎] %s 执行周一全量调仓", researcher.name)
        _last_rotation_date[rid] = today_str

        target_pool = generate_target_pool_from_quotes(
            config,
            all_quotes,
            blacklist=_not_buy_again[rid],
        )
        target_symbols = {t["symbol"] for t in target_pool}

        for symbol, pos in list(current_positions.items()):
            if symbol not in target_symbols and symbol not in high_limit_list:
                quote = realtime_quote_map.get(symbol)
                sell_price = realtime_price_map.get(symbol, pos.current_price)
                sc, pnl = await do_sell(
                    session,
                    researcher,
                    account,
                    pos,
                    sell_price,
                    quote,
                    close_commission_rate,
                    close_tax_rate,
                    min_commission,
                    "轮动调出目标池，执行卖出",
                )
                trade_count += sc
                sell_count += sc
                daily_pnl += pnl
                if sc > 0:
                    del current_positions[symbol]

        new_targets = [t for t in target_pool if t["symbol"] not in current_positions]
        if new_targets and account.available_cash > 1000:
            stock_count = config.get("stock_count", 10)
            position_count = len(current_positions)
            if stock_count > position_count:
                per_stock_budget = account.available_cash / (stock_count - position_count)
                for target in new_targets:
                    bc, pnl = await do_buy(
                        session,
                        researcher,
                        account,
                        target,
                        per_stock_budget,
                        open_commission_rate,
                        min_commission,
                    )
                    trade_count += bc
                    buy_count += bc
                    daily_pnl += pnl
                    if len(current_positions) + buy_count >= stock_count:
                        break
    else:
        logger.info("[策略引擎] %s 非调仓日，执行止损检查", researcher.name)
        for symbol, pos in list(current_positions.items()):
            cur_price = realtime_price_map.get(symbol, pos.current_price)
            if pos.cost_price > 0:
                pnl_pct = (cur_price - pos.cost_price) / pos.cost_price
                if pnl_pct <= stop_loss:
                    reason = f"触发止损线（当前亏损 {pnl_pct:.1%}，止损阈值 {stop_loss:.0%}）"
                    sc, pnl = await do_sell(
                        session,
                        researcher,
                        account,
                        pos,
                        cur_price,
                        realtime_quote_map.get(symbol),
                        close_commission_rate,
                        close_tax_rate,
                        min_commission,
                        reason,
                    )
                    trade_count += sc
                    sell_count += sc
                    daily_pnl += pnl
                    if sc > 0:
                        del current_positions[symbol]

    for symbol, pos in current_positions.items():
        new_price = realtime_price_map.get(symbol, pos.current_price)
        old_pnl = pos.pnl
        pos.current_price = new_price
        pos.pnl = round((new_price - pos.cost_price) * pos.quantity, 2)
        daily_pnl += pos.pnl - old_pnl

    all_pos_stmt = select(Position).where(Position.account_id == account.id)
    all_pos_result = await session.execute(all_pos_stmt)
    all_positions = list(all_pos_result.scalars().all())
    account.holding_value = sum(p.current_price * p.quantity for p in all_positions)
    account.total_asset = account.available_cash + account.holding_value
    account.daily_pnl = round(daily_pnl, 2)
    researcher.today_pnl = round(daily_pnl, 2)

    session.add(
        TradeLog(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="analysis",
            trade_record_ids="[]",
            title="当前操作情况总结",
            content=_gen_daily_summary(
                sell_count,
                buy_count,
                daily_pnl,
                account.total_asset,
                account.available_cash,
                [p.name for p in all_positions],
            ),
        )
    )

    await session.commit()
    invalidate_trading_cache(account, researcher.id)
    return trade_count
