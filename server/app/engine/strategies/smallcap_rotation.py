from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime
from uuid import uuid4

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.paper_trading.executor import do_buy, do_sell, invalidate_trading_cache
from app.engine.paper_trading.state import set_limit_up_symbols
from app.engine.strategies.market import fetch_realtime_quotes
from app.integrations.akshare.client import get_stock_history, run_sync
from app.integrations.openclaw.trade_push import (
    discard_strategy_trade_pushes,
    flush_strategy_trade_pushes,
)
from app.models.researcher import Researcher
from app.models.trading import Position, TradeLog, TradingAccount

logger = logging.getLogger(__name__)

STRATEGY_TYPE = "smallcap_rotation"
BLACKLIST_DAYS = 20
DEFAULT_STOCK_COUNT = 10

_hold_history: dict[str, list[list[str]]] = defaultdict(list)
_not_buy_again: dict[str, set[str]] = defaultdict(set)
_last_adjustment_date: dict[str, str] = {}


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_symbol(symbol: str) -> str:
    symbol = str(symbol or "").strip()
    if "." in symbol:
        return symbol.split(".", 1)[0]
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol[2:]
    return symbol


def _listed_date(raw: object) -> date | None:
    if isinstance(raw, date):
        return raw
    if not raw:
        return None
    text = str(raw).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
        except ValueError:
            continue
    return None


def _is_kcb(symbol: str) -> bool:
    return symbol.startswith("688")


def _is_bj(symbol: str) -> bool:
    return symbol.startswith(("8", "4", "920", "830", "870"))


def _is_st(name: str, explicit: object = None) -> bool:
    if explicit is not None:
        return bool(explicit)
    upper = str(name or "").upper()
    return "ST" in upper or "*" in upper or "退" in upper


def _is_new_stock(stock: dict, as_of: date, days: int) -> bool:
    start = _listed_date(stock.get("start_date") or stock.get("listed_date"))
    if start is None:
        return False
    return (as_of - start).days < days


def _is_paused(stock: dict) -> bool:
    if "paused" in stock:
        return bool(stock.get("paused"))
    return _to_float(stock.get("volume")) <= 0


def _limit_price(stock: dict, side: str) -> float:
    explicit = stock.get("high_limit" if side == "up" else "low_limit")
    if explicit:
        return _to_float(explicit)
    prev_close = _to_float(stock.get("prev_close"))
    if prev_close <= 0:
        return 0.0
    symbol = str(stock.get("symbol") or "")
    ratio = 0.20 if symbol.startswith(("300", "301", "688", "689")) else 0.10
    return round(prev_close * (1 + ratio if side == "up" else 1 - ratio), 2)


def _strict_factor_universe(strategy_config: dict, all_quotes: list[dict]) -> list[dict]:
    """Return records with the same semantic fields used by the original JQ strategy.

    The original strategy depends on JQ factors. We accept those values from
    strategy_config["factor_universe"] or from enriched quote records. We do not
    substitute price momentum/PE/volume-ratio for financial factors.
    """
    configured = strategy_config.get("factor_universe")
    source = configured if isinstance(configured, list) and configured else all_quotes
    quote_by_symbol = {_normalize_symbol(q.get("symbol", "")): q for q in all_quotes}
    out: list[dict] = []
    for item in source:
        if not isinstance(item, dict):
            continue
        symbol = _normalize_symbol(str(item.get("symbol") or item.get("code") or ""))
        if not symbol:
            continue
        quote = quote_by_symbol.get(symbol, {})
        merged = {**quote, **item}
        merged["symbol"] = symbol
        merged["name"] = str(merged.get("name") or merged.get("display_name") or symbol)
        merged["price"] = _to_float(merged.get("price") or merged.get("last_price"))
        merged["prev_close"] = _to_float(merged.get("prev_close"))
        merged["volume"] = _to_float(merged.get("volume"))
        merged["amount"] = _to_float(merged.get("amount"))
        merged["circulating_market_cap"] = _to_float(merged.get("circulating_market_cap"))
        merged["eps"] = _to_float(merged.get("eps"))
        for key in (
            "sales_growth",
            "operating_revenue_growth_rate",
            "total_profit_growth_rate",
            "net_profit_growth_rate",
            "earnings_growth",
            "PEG",
            "turnover_volatility",
        ):
            merged[key] = _to_float(merged.get(key), default=float("nan"))
        out.append(merged)
    return out


def _has_required_factor_data(stocks: list[dict]) -> bool:
    required = (
        "sales_growth",
        "operating_revenue_growth_rate",
        "total_profit_growth_rate",
        "net_profit_growth_rate",
        "earnings_growth",
        "PEG",
        "turnover_volatility",
        "eps",
        "circulating_market_cap",
    )
    return any(all(pd.notna(stock.get(key)) for key in required) for stock in stocks)


def _filter_initial_universe(strategy_config: dict, stocks: list[dict], as_of: date) -> list[dict]:
    filters = strategy_config.get("filters", {})
    new_days = int(filters.get("exclude_new_days", 375))
    result: list[dict] = []
    for stock in stocks:
        symbol = stock["symbol"]
        if filters.get("exclude_bj", True) and _is_bj(symbol):
            continue
        if filters.get("exclude_kcb", True) and _is_kcb(symbol):
            continue
        if filters.get("exclude_st", True) and _is_st(stock.get("name", ""), stock.get("is_st")):
            continue
        if filters.get("exclude_new_days", 375) and _is_new_stock(stock, as_of, new_days):
            continue
        result.append(stock)
    return result


def _factor_filter_list(stocks: list[dict], factor: str, ascending: bool, p1: float, p2: float) -> list[dict]:
    scored = [s for s in stocks if pd.notna(s.get(factor))]
    scored.sort(key=lambda s: _to_float(s.get(factor)), reverse=not ascending)
    start = int(p1 * len(stocks))
    end = int(p2 * len(stocks))
    return scored[start:end]


def _sort_by_cap_positive_eps(stocks: list[dict]) -> list[dict]:
    filtered = [
        s for s in stocks
        if _to_float(s.get("eps")) > 0 and _to_float(s.get("circulating_market_cap")) > 0
    ]
    filtered.sort(key=lambda s: _to_float(s.get("circulating_market_cap")))
    return filtered


def _pool_sg(initial_list: list[dict]) -> list[dict]:
    sg_candidates = _factor_filter_list(initial_list, "sales_growth", ascending=False, p1=0, p2=0.1)
    return _sort_by_cap_positive_eps(sg_candidates)


def _pool_ms(initial_list: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for stock in initial_list:
        required = [
            stock.get("operating_revenue_growth_rate"),
            stock.get("total_profit_growth_rate"),
            stock.get("net_profit_growth_rate"),
            stock.get("earnings_growth"),
        ]
        if any(pd.isna(v) for v in required):
            continue
        item = dict(stock)
        item["total_score"] = (
            0.10 * _to_float(stock.get("operating_revenue_growth_rate"))
            + 0.35 * _to_float(stock.get("total_profit_growth_rate"))
            + 0.15 * _to_float(stock.get("net_profit_growth_rate"))
            + 0.40 * _to_float(stock.get("earnings_growth"))
        )
        rows.append(item)
    rows.sort(key=lambda s: _to_float(s.get("total_score")), reverse=True)
    complex_growth_list = rows[: int(0.1 * len(rows))]
    return _sort_by_cap_positive_eps(complex_growth_list)


def _pool_peg(initial_list: list[dict]) -> list[dict]:
    peg_candidates = _factor_filter_list(initial_list, "PEG", ascending=True, p1=0, p2=0.2)
    turnover_candidates = _factor_filter_list(
        peg_candidates,
        "turnover_volatility",
        ascending=True,
        p1=0,
        p2=0.5,
    )
    return _sort_by_cap_positive_eps(turnover_candidates)


def get_stock_list(strategy_config: dict, all_quotes: list[dict], as_of: date | None = None) -> list[list[dict]]:
    as_of = as_of or date.today()
    initial_list = _strict_factor_universe(strategy_config, all_quotes)
    initial_list = _filter_initial_universe(strategy_config, initial_list, as_of)
    logger.info("[小市值] 初始股票池 %d", len(initial_list))
    return [_pool_sg(initial_list), _pool_ms(initial_list), _pool_peg(initial_list)]


def _filter_paused_stock(stock_list: list[dict]) -> list[dict]:
    return [stock for stock in stock_list if not _is_paused(stock)]


def _filter_limitup_stock(stock_list: list[dict], current_positions: set[str] | None = None) -> list[dict]:
    current_positions = current_positions or set()
    out: list[dict] = []
    for stock in stock_list:
        if stock["symbol"] in current_positions:
            out.append(stock)
            continue
        high_limit = _limit_price(stock, "up")
        if high_limit <= 0 or _to_float(stock.get("price")) < high_limit:
            out.append(stock)
    return out


def _filter_limitdown_stock(stock_list: list[dict], current_positions: set[str] | None = None) -> list[dict]:
    current_positions = current_positions or set()
    out: list[dict] = []
    for stock in stock_list:
        if stock["symbol"] in current_positions:
            out.append(stock)
            continue
        low_limit = _limit_price(stock, "down")
        if low_limit <= 0 or _to_float(stock.get("price")) > low_limit:
            out.append(stock)
    return out


def _recent_limit_up_from_history(symbol: str, recent_days: int, end_date: date) -> bool:
    from datetime import timedelta

    try:
        bars = get_stock_history(
            symbol,
            end_date=end_date,
            start_date=end_date - timedelta(days=recent_days * 2 + 10),
            adjust="",
        )
    except Exception:
        logger.exception("[小市值] 获取历史涨停失败：%s", symbol)
        return False
    recent = bars[-recent_days:]
    for bar in recent:
        previous_close = bar.close / (1 + bar.change_pct / 100) if bar.change_pct else 0.0
        ratio = 0.20 if symbol.startswith(("300", "301", "688", "689")) else 0.10
        high_limit = round(previous_close * (1 + ratio), 2) if previous_close > 0 else 0.0
        if high_limit > 0 and bar.close >= high_limit:
            return True
    return False


def _recent_limit_up_from_records(stock_list: list[dict], recent_days: int, as_of: date) -> set[str]:
    result: set[str] = set()
    for stock in stock_list:
        symbol = stock["symbol"]
        if stock.get("recent_limit_up"):
            result.add(symbol)
            continue
        history = stock.get("history")
        if isinstance(history, list):
            for row in history[-recent_days:]:
                close = _to_float(row.get("close") if isinstance(row, dict) else getattr(row, "close", 0))
                high_limit = _to_float(row.get("high_limit") if isinstance(row, dict) else getattr(row, "high_limit", 0))
                if high_limit > 0 and close == high_limit:
                    result.add(symbol)
                    break
            continue
        if strategy_uses_live_history(stock) and _recent_limit_up_from_history(symbol, recent_days, as_of):
            result.add(symbol)
    return result


def strategy_uses_live_history(stock: dict) -> bool:
    return bool(stock.get("use_live_history"))


def generate_target_pool_from_quotes(
    strategy_config: dict,
    all_quotes: list[dict],
    count: int = DEFAULT_STOCK_COUNT,
    blacklist: set[str] | None = None,
    as_of: date | None = None,
    current_positions: set[str] | None = None,
) -> list[dict]:
    as_of = as_of or date.today()
    stock_num = int(strategy_config.get("stock_count") or count)
    all_list = get_stock_list(strategy_config, all_quotes, as_of)
    sg_list = all_list[0][:5]
    ms_list = all_list[1][:5]
    peg_list = all_list[2][:5]

    by_symbol: dict[str, dict] = {}
    for stock in sg_list + ms_list + peg_list:
        by_symbol.setdefault(stock["symbol"], stock)
    union_list = list(by_symbol.values())
    union_list = _sort_by_cap_positive_eps(union_list)
    union_list = _filter_paused_stock(union_list)
    union_list = _filter_limitup_stock(union_list, current_positions)
    union_list = _filter_limitdown_stock(union_list, current_positions)

    recent_days = int(strategy_config.get("blacklist", {}).get("lookback_days") or BLACKLIST_DAYS)
    recent_limit_up = _recent_limit_up_from_records(union_list, recent_days, as_of)
    effective_blacklist = (blacklist or set()).intersection(recent_limit_up)
    if effective_blacklist:
        union_list = [stock for stock in union_list if stock["symbol"] not in effective_blacklist]

    target_list = union_list[: min(stock_num, len(union_list))]
    logger.info(
        "[小市值] SG %d / MS %d / PEG %d / 并集 %d / 黑名单 %d / 目标 %d",
        len(sg_list),
        len(ms_list),
        len(peg_list),
        len(by_symbol),
        len(effective_blacklist),
        len(target_list),
    )
    return [
        {
            "symbol": stock["symbol"],
            "name": stock["name"],
            "price": _to_float(stock.get("price")),
            "prev_close": _to_float(stock.get("prev_close")),
            "volume": _to_float(stock.get("volume")),
            "reason": "符合小市值SG/MS/PEG选股条件",
        }
        for stock in target_list
    ]


def generate_target_pool(strategy_config: dict, count: int = DEFAULT_STOCK_COUNT) -> list[dict]:
    return generate_target_pool_from_quotes(strategy_config, fetch_realtime_quotes(), count)


async def _fetch_realtime_quotes_async() -> list[dict]:
    return await run_sync(fetch_realtime_quotes)


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
        lines.append("今日无调仓操作，当前持仓符合目标池或策略数据不足，继续按纪律观察。\n")
    else:
        lines.append(f"本次按照小市值SG/MS/PEG策略完成调仓：卖出 {sell_count} 笔，买入 {buy_count} 笔。\n")
    lines.append(f"今日策略盈亏 **{total_pnl:+,.2f} 元**。\n")
    lines.append(f"当前账户总资产 {total_asset:,.2f} 元，可用资金 {available_cash:,.2f} 元。")
    if hold_names:
        lines.append(f"\n\n当前持仓 {len(hold_names)} 只：{'、'.join(hold_names)}。")
    return "\n".join(lines)


async def _load_account(session: AsyncSession, researcher: Researcher) -> TradingAccount:
    acct_stmt = select(TradingAccount).where(TradingAccount.researcher_id == researcher.id)
    acct_result = await session.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()
    if account:
        return account

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
    return account


async def _load_positions(session: AsyncSession, account_id: str) -> dict[str, Position]:
    pos_stmt = select(Position).where(Position.account_id == account_id)
    pos_result = await session.execute(pos_stmt)
    return {p.symbol: p for p in pos_result.scalars().all()}


async def execute(session: AsyncSession, researcher: Researcher) -> int:
    config = researcher.strategy_config or {}
    cost_config = config.get("cost", {})
    open_commission_rate = cost_config.get("open_commission", 0.0003)
    close_commission_rate = cost_config.get("close_commission", 0.0003)
    close_tax_rate = cost_config.get("close_tax", 0.001)
    min_commission = cost_config.get("min_commission", 5)
    rid = researcher.id

    from zoneinfo import ZoneInfo

    today = datetime.now(tz=ZoneInfo("Asia/Shanghai")).date()
    today_str = today.isoformat()
    if _last_adjustment_date.get(rid) == today_str:
        logger.info("[小市值] %s 今日已调仓，跳过重复执行", researcher.name)
        return 0

    account = await _load_account(session, researcher)
    current_positions = await _load_positions(session, account.id)
    hold_symbols = list(current_positions.keys())

    _hold_history[rid].append(hold_symbols)
    if len(_hold_history[rid]) > BLACKLIST_DAYS:
        _hold_history[rid] = _hold_history[rid][-BLACKLIST_DAYS:]
    _not_buy_again[rid] = {symbol for item in _hold_history[rid] for symbol in item}

    all_quotes = await _fetch_realtime_quotes_async()
    factor_universe = _strict_factor_universe(config, all_quotes)
    if not _has_required_factor_data(factor_universe):
        logger.warning("[小市值] %s 缺少原策略因子数据，跳过本次调仓", researcher.name)
        return 0

    realtime_quote_map: dict[str, dict] = {q["symbol"]: q for q in all_quotes}
    realtime_price_map: dict[str, float] = {q["symbol"]: q["price"] for q in all_quotes}

    high_limit_list: list[str] = []
    for symbol in hold_symbols:
        quote = realtime_quote_map.get(symbol)
        if not quote:
            continue
        high_limit = _limit_price(quote, "up")
        if high_limit > 0 and _to_float(quote.get("price")) >= high_limit:
            high_limit_list.append(symbol)
    set_limit_up_symbols(rid, high_limit_list)

    trade_count = 0
    daily_pnl = 0.0
    sell_count = 0
    buy_count = 0

    target_pool = generate_target_pool_from_quotes(
        config,
        all_quotes,
        blacklist=_not_buy_again[rid],
        as_of=today,
        current_positions=set(current_positions),
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
                "不在目标买入列表",
            )
            trade_count += sc
            sell_count += sc
            daily_pnl += pnl
            if sc > 0:
                del current_positions[symbol]

    new_targets = [target for target in target_pool if target["symbol"] not in current_positions]
    target_num = len(target_pool)
    position_count = len(current_positions)
    if target_num > position_count and account.available_cash > 1000:
        cash_per_stock = account.available_cash / (target_num - position_count)
        for target in new_targets:
            bc, pnl = await do_buy(
                session,
                researcher,
                account,
                target,
                cash_per_stock,
                open_commission_rate,
                min_commission,
            )
            trade_count += bc
            buy_count += bc
            daily_pnl += pnl
            if len(current_positions) + buy_count >= target_num:
                break

    await _mark_to_market_and_commit(
        session,
        researcher,
        account,
        current_positions,
        realtime_price_map,
        daily_pnl,
        sell_count,
        buy_count,
    )
    _last_adjustment_date[rid] = today_str
    return trade_count


async def execute_stop_loss(session: AsyncSession, researcher: Researcher) -> int:
    config = researcher.strategy_config or {}
    stop_loss = config.get("risk_control", {}).get("stop_loss", -0.10)
    cost_config = config.get("cost", {})
    close_commission_rate = cost_config.get("close_commission", 0.0003)
    close_tax_rate = cost_config.get("close_tax", 0.001)
    min_commission = cost_config.get("min_commission", 5)

    account = await _load_account(session, researcher)
    current_positions = await _load_positions(session, account.id)
    all_quotes = await _fetch_realtime_quotes_async()
    realtime_quote_map: dict[str, dict] = {q["symbol"]: q for q in all_quotes}
    realtime_price_map: dict[str, float] = {q["symbol"]: q["price"] for q in all_quotes}

    trade_count = 0
    daily_pnl = 0.0
    for symbol, pos in list(current_positions.items()):
        cur_price = realtime_price_map.get(symbol, pos.current_price)
        if pos.cost_price <= 0:
            continue
        loss_ratio = cur_price / pos.cost_price - 1
        if loss_ratio <= stop_loss:
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
                f"触发止损 (亏损比例: {loss_ratio * 100:.2f}%)",
            )
            trade_count += sc
            daily_pnl += pnl
            if sc > 0:
                del current_positions[symbol]

    if trade_count > 0:
        await _mark_to_market_and_commit(
            session,
            researcher,
            account,
            current_positions,
            realtime_price_map,
            daily_pnl,
            trade_count,
            0,
        )
    return trade_count


async def _mark_to_market_and_commit(
    session: AsyncSession,
    researcher: Researcher,
    account: TradingAccount,
    current_positions: dict[str, Position],
    realtime_price_map: dict[str, float],
    daily_pnl: float,
    sell_count: int,
    buy_count: int,
) -> None:
    for symbol, pos in current_positions.items():
        new_price = realtime_price_map.get(symbol, pos.current_price)
        old_pnl = pos.pnl
        pos.current_price = new_price
        pos.pnl = round((new_price - pos.cost_price) * pos.quantity, 2)
        daily_pnl += pos.pnl - old_pnl

    all_positions = await _load_positions(session, account.id)
    account.holding_value = sum(p.current_price * p.quantity for p in all_positions.values())
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
                [p.name for p in all_positions.values()],
            ),
        )
    )
    try:
        await session.commit()
    except Exception:
        discard_strategy_trade_pushes(session)
        raise
    invalidate_trading_cache(account, researcher.id)
    await flush_strategy_trade_pushes(session)
