"""
模拟盘历史数据补全脚本 —— 合成式 backfill

背景：
  现有 strategies/* 是为"实时跑当天"设计的（fetch_realtime_quotes / datetime.now），
  不能直接当历史回放器用。为了在演示库里把每个研究员的模拟盘数据补到看起来"真实"，
  本脚本采取合成式思路：
    1. 从研究员 strategy_config 读取 stock_count、universe（缺失则用回退白名单）
    2. 用 akshare 历史日 K（前复权）做"过去 N 个交易日"的回放
    3. 第一天等权建仓；每周一按 30 日动量调仓换 1~2 只；每日检查 -10% 硬止损
    4. 每周一最后一笔交易后调用 TradingReflectionSkill 生成 1 条 AI 复盘日志
    5. 跑完用最后一个交易日收盘价同步 positions.current_price 与账户 holding_value

用法：
    cd server
    # 1) dry-run（默认）：只列出将要产生的成交，不写库
    python -m scripts.backfill_paper_trading --days 30

    # 2) 真写入：补全全部研究员
    python -m scripts.backfill_paper_trading --days 30 --commit

    # 3) 只补某一个研究员
    python -m scripts.backfill_paper_trading --researcher-id r_xxxxxxxxxx --commit

参数：
    --days N              回放最近 N 个交易日，默认 30
    --researcher-id X     只补指定研究员，默认全部
    --commit              真正写库；不带则 dry-run
    --skip-reflection     跳过 LLM 复盘日志（dev 时省钱）
    --keep-existing       保留 30 天内已有的 trade_records / trade_logs / positions（默认会先清空再补）

注意：
  * 演示库专用。脚本默认会先清空目标账户在 [start_date, today] 区间内的
    trade_records / trade_logs，并清空当前 positions（按账户）。生产环境请勿运行。
  * 不调用 do_buy / do_sell（它们每次写 1 条 trade + 1 条 analysis 日志，开销大）。
    这里直接 INSERT，每周末批量调用 reflection_skill 一次。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.integrations.akshare.client import (
    HistoryBar,
    get_stock_history,
    get_stock_history_batch,
    list_recent_trade_dates,
    run_sync,
)
from app.models.researcher import Researcher
from app.models.trading import Position, TradeLog, TradeRecord, TradingAccount
from app.modules.trading.reflection_skill import TradingReflectionSkill

logger = logging.getLogger("backfill_paper_trading")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ── 常量 ──
OPEN_COMM_RATE = 0.0003
CLOSE_COMM_RATE = 0.0003
CLOSE_TAX_RATE = 0.001
MIN_COMMISSION = 5.0
HARD_STOP_LOSS_PCT = -0.10  # 当日最低价跌穿成本 10% 触发止损（按收盘价回写）

# 回退股票池：流动性好、akshare 一定能拿到日 K
FALLBACK_UNIVERSE: list[tuple[str, str]] = [
    ("600519", "贵州茅台"),
    ("000858", "五粮液"),
    ("600036", "招商银行"),
    ("601318", "中国平安"),
    ("000333", "美的集团"),
    ("000651", "格力电器"),
    ("600276", "恒瑞医药"),
    ("002594", "比亚迪"),
    ("300750", "宁德时代"),
    ("600030", "中信证券"),
    ("601012", "隆基绿能"),
    ("600887", "伊利股份"),
    ("002415", "海康威视"),
    ("000725", "京东方A"),
    ("600585", "海螺水泥"),
    ("600009", "上海机场"),
    ("600900", "长江电力"),
    ("601166", "兴业银行"),
    ("600028", "中国石化"),
    ("601398", "工商银行"),
]

SENTIMENT_UNIVERSE: list[tuple[str, str]] = [
    ("000063", "中兴通讯"),
    ("000158", "常山北明"),
    ("000938", "紫光股份"),
    ("000977", "浪潮信息"),
    ("002031", "巨轮智能"),
    ("002085", "万丰奥威"),
    ("002156", "通富微电"),
    ("002230", "科大讯飞"),
    ("002236", "大华股份"),
    ("002281", "光迅科技"),
    ("002371", "北方华创"),
    ("002463", "沪电股份"),
    ("002555", "三七互娱"),
    ("300502", "新易盛"),
    ("600536", "中国软件"),
    ("600580", "卧龙电驱"),
    ("600839", "四川长虹"),
    ("603019", "中科曙光"),
    ("603501", "韦尔股份"),
    ("603986", "兆易创新"),
]

_reflection_skill = TradingReflectionSkill()
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


# ────────────────────────────────────────────────────────────
# 数据结构
# ────────────────────────────────────────────────────────────

@dataclass
class HoldingState:
    """回放过程中的内存持仓状态。"""
    symbol: str
    name: str
    quantity: int
    cost_price: float
    entry_idx: int = 0


@dataclass
class PendingTrade:
    """一笔待落库的成交。"""
    trade_date: date
    symbol: str
    name: str
    side: str            # buy / sell
    quantity: int
    price: float
    commission: float
    realized_pnl: float | None = None  # sell 才有
    cost_price: float | None = None    # sell 才有
    reason: str = ""


@dataclass
class WeeklyReflectionInput:
    """每周一条复盘日志的素材。"""
    week_end: date
    summary_context: dict


@dataclass
class ResearcherBackfillResult:
    researcher_id: str
    researcher_name: str
    trades: list[PendingTrade]
    final_positions: dict[str, HoldingState]
    final_cash: float
    weekly_reflections: list[WeeklyReflectionInput]


# ────────────────────────────────────────────────────────────
# 选股池工具
# ────────────────────────────────────────────────────────────

def resolve_universe(strategy_config: dict | None) -> list[tuple[str, str]]:
    """从 strategy_config.universe 取股票池；缺失则用回退白名单。"""
    if not strategy_config:
        return list(FALLBACK_UNIVERSE)
    if strategy_config.get("strategy_type") == "sentiment_ultrashort":
        return list(SENTIMENT_UNIVERSE)
    universe = strategy_config.get("universe")
    if not universe:
        return list(FALLBACK_UNIVERSE)
    out: list[tuple[str, str]] = []
    for item in universe:
        if isinstance(item, dict):
            symbol = str(item.get("symbol") or "").strip()
            name = str(item.get("name") or symbol).strip()
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            symbol = str(item[0]).strip()
            name = str(item[1]).strip()
        else:
            symbol = str(item).strip()
            name = symbol
        if symbol:
            out.append((symbol, name))
    return out or list(FALLBACK_UNIVERSE)


def stock_count_of(strategy_config: dict | None) -> int:
    """读 strategy_config.stock_count，默认 10，clip 到 [1, 20]。"""
    n = 10
    if isinstance(strategy_config, dict):
        try:
            n = int(strategy_config.get("stock_count") or 10)
        except Exception:
            n = 10
    return max(1, min(20, n))


def _exchange_prefixed_symbol(symbol: str) -> str:
    """AKShare stock_zh_a_daily 需要 sh/sz/bj 前缀。"""
    symbol = symbol.strip()
    if symbol.startswith(("sh", "sz", "bj")):
        return symbol
    if symbol.startswith("6"):
        return f"sh{symbol}"
    if symbol.startswith(("0", "3")):
        return f"sz{symbol}"
    if symbol.startswith(("4", "8")):
        return f"bj{symbol}"
    return symbol


def _fetch_history_with_daily_api(
    symbol: str,
    start_date: date,
    end_date: date,
    *,
    adjust: str = "qfq",
) -> list[HistoryBar]:
    """用新浪日线接口拉历史行情，作为 backfill 的稳定主数据源。"""
    import akshare as ak
    import pandas as pd

    prefixed = _exchange_prefixed_symbol(symbol)
    df = ak.stock_zh_a_daily(
        symbol=prefixed,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        adjust=adjust,
    )
    if df is None or df.empty:
        return []

    bars: list[HistoryBar] = []
    prev_close: float | None = None
    for _, row in df.sort_values("date").iterrows():
        raw_date = row.get("date")
        try:
            date_str = pd.to_datetime(raw_date).strftime("%Y-%m-%d")
        except Exception:
            date_str = str(raw_date)[:10]

        close = float(row.get("close") or 0.0)
        if prev_close and prev_close > 0:
            change_pct = (close - prev_close) / prev_close * 100
        else:
            change_pct = 0.0
        turnover = float(row.get("turnover") or 0.0)
        if 0 < turnover < 1:
            turnover *= 100

        bars.append(HistoryBar(
            symbol=symbol,
            date=date_str,
            open=float(row.get("open") or 0.0),
            close=close,
            high=float(row.get("high") or 0.0),
            low=float(row.get("low") or 0.0),
            volume=float(row.get("volume") or 0.0),
            amount=float(row.get("amount") or 0.0),
            change_pct=round(change_pct, 4),
            turnover=turnover,
        ))
        prev_close = close
    return bars


def get_stock_history_batch_for_backfill(
    symbols: list[str],
    start_date: date,
    end_date: date,
    *,
    adjust: str = "qfq",
    retries: int = 3,
) -> dict[str, list[HistoryBar]]:
    """补模拟盘专用：逐股重试并节流，避免行情源短时断连导致空回放。"""
    result: dict[str, list[HistoryBar]] = {}
    for symbol in sorted({s for s in symbols if s}):
        bars: list[HistoryBar] = []
        for attempt in range(1, retries + 1):
            try:
                bars = _fetch_history_with_daily_api(
                    symbol,
                    start_date,
                    end_date,
                    adjust=adjust,
                )
            except Exception as exc:
                logger.warning(
                    "新浪历史日 K 拉取失败：%s %s~%s，第 %d/%d 次：%s",
                    symbol,
                    start_date,
                    end_date,
                    attempt,
                    retries,
                    exc,
                )
            if bars:
                break
            time.sleep(0.4 * attempt)

        if not bars:
            bars = get_stock_history(symbol, start_date, end_date, adjust=adjust)
        result[symbol] = bars
        time.sleep(0.15)

    return result


# ────────────────────────────────────────────────────────────
# 单个研究员的回放
# ────────────────────────────────────────────────────────────

def _round_lot(quantity: int) -> int:
    """A 股 100 股一手。"""
    return (quantity // 100) * 100


def _buy_commission(amount: float) -> float:
    return max(MIN_COMMISSION, amount * OPEN_COMM_RATE)


def _sell_commission(amount: float) -> float:
    return max(MIN_COMMISSION, amount * CLOSE_COMM_RATE) + amount * CLOSE_TAX_RATE


def _bar_lookup(bars: list[HistoryBar]) -> dict[str, HistoryBar]:
    return {b.date: b for b in bars}


def _momentum_score(bars: list[HistoryBar], as_of: date) -> float | None:
    """简单动量：截止 as_of 之前最近 20 根 K 线的累计涨幅。"""
    cutoff = as_of.isoformat()
    series = [b for b in bars if b.date <= cutoff]
    if len(series) < 5:
        return None
    window = series[-20:] if len(series) >= 20 else series
    first = window[0].close
    last = window[-1].close
    if first <= 0:
        return None
    return (last - first) / first


def replay_one_researcher(
    *,
    researcher: Researcher,
    trade_dates: list[date],
    universe_bars: dict[str, list[HistoryBar]],
    initial_cash: float,
) -> ResearcherBackfillResult:
    """对单个研究员做合成式回放，返回所有待落库的事件。"""
    if not trade_dates:
        return ResearcherBackfillResult(
            researcher_id=researcher.id,
            researcher_name=researcher.name,
            trades=[],
            final_positions={},
            final_cash=initial_cash,
            weekly_reflections=[],
        )

    target_n = stock_count_of(researcher.strategy_config)
    cash = float(initial_cash)
    holdings: dict[str, HoldingState] = {}
    trades: list[PendingTrade] = []
    weekly_inputs: list[WeeklyReflectionInput] = []

    universe_meta = {symbol: bars for symbol, bars in universe_bars.items() if bars}
    name_lookup: dict[str, str] = {}
    for symbol, bars in universe_meta.items():
        # name 来自 universe 元信息（在外层注入 .symbol/name 时设置）；这里 fallback 用代码
        name_lookup[symbol] = symbol

    def candidates_at(d: date, top_n: int) -> list[str]:
        scored: list[tuple[str, float]] = []
        for symbol, bars in universe_meta.items():
            score = _momentum_score(bars, d)
            if score is None:
                continue
            scored.append((symbol, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [s for s, _ in scored[:top_n]]

    def price_at(symbol: str, d: date, kind: str = "close") -> float | None:
        bars = universe_meta.get(symbol)
        if not bars:
            return None
        for b in bars:
            if b.date == d.isoformat():
                return getattr(b, kind, b.close)
        return None

    def low_at(symbol: str, d: date) -> float | None:
        return price_at(symbol, d, kind="low")

    # ── 第 1 天：等权建仓 ──
    first_day = trade_dates[0]
    initial_picks = candidates_at(first_day, target_n)
    if not initial_picks:
        logger.warning("[%s] 第一天 %s 无任何候选股价格，跳过", researcher.name, first_day)
        return ResearcherBackfillResult(
            researcher_id=researcher.id,
            researcher_name=researcher.name,
            trades=[],
            final_positions={},
            final_cash=initial_cash,
            weekly_reflections=[],
        )
    per_stock_budget = cash / len(initial_picks)
    for symbol in initial_picks:
        price = price_at(symbol, first_day, "open") or price_at(symbol, first_day, "close")
        if not price or price <= 0:
            continue
        qty = _round_lot(int(per_stock_budget / price))
        if qty < 100:
            continue
        amount = qty * price
        comm = _buy_commission(amount)
        if cash < amount + comm:
            continue
        cash -= amount + comm
        holdings[symbol] = HoldingState(
            symbol=symbol,
            name=name_lookup.get(symbol, symbol),
            quantity=qty,
            cost_price=price,
        )
        trades.append(PendingTrade(
            trade_date=first_day,
            symbol=symbol,
            name=name_lookup.get(symbol, symbol),
            side="buy",
            quantity=qty,
            price=round(price, 4),
            commission=round(comm, 2),
            reason="建仓：按 30 日动量等权配置",
        ))

    # ── 后续每天：止损 + 周一调仓 ──
    weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
    for d in trade_dates:
        iso = d.isocalendar()
        weeks[(iso.year, iso.week)].append(d)

    for d in trade_dates[1:]:
        # 1) 止损扫描：当日最低价跌穿成本 10% → 按当日收盘价卖出
        for symbol in list(holdings.keys()):
            pos = holdings[symbol]
            low = low_at(symbol, d)
            close = price_at(symbol, d, "close")
            if low is None or close is None:
                continue
            if pos.cost_price <= 0:
                continue
            drawdown = (low - pos.cost_price) / pos.cost_price
            if drawdown <= HARD_STOP_LOSS_PCT:
                amount = pos.quantity * close
                comm = _sell_commission(amount)
                realized = (close - pos.cost_price) * pos.quantity - comm
                cash += amount - comm
                trades.append(PendingTrade(
                    trade_date=d,
                    symbol=symbol,
                    name=pos.name,
                    side="sell",
                    quantity=pos.quantity,
                    price=round(close, 4),
                    commission=round(comm, 2),
                    realized_pnl=round(realized, 2),
                    cost_price=round(pos.cost_price, 4),
                    reason=f"硬止损：当日最低价回撤 {drawdown:.2%}",
                ))
                del holdings[symbol]

        # 2) 周一调仓
        if d.weekday() == 0:
            ranking = candidates_at(d, max(target_n + 3, target_n))
            if ranking:
                target_set = set(ranking[:target_n])
                # 卖出：当前持仓里不在新目标的；优先剔除动量最弱的
                hold_scored: list[tuple[str, float]] = []
                for symbol in list(holdings.keys()):
                    if symbol in target_set:
                        continue
                    score = _momentum_score(universe_meta.get(symbol, []), d) or -999.0
                    hold_scored.append((symbol, score))
                hold_scored.sort(key=lambda x: x[1])
                # 每周只换 1~2 只，避免日志过密
                to_sell = hold_scored[:min(2, len(hold_scored))]
                for symbol, _ in to_sell:
                    pos = holdings[symbol]
                    close = price_at(symbol, d, "close")
                    if not close:
                        continue
                    amount = pos.quantity * close
                    comm = _sell_commission(amount)
                    realized = (close - pos.cost_price) * pos.quantity - comm
                    cash += amount - comm
                    trades.append(PendingTrade(
                        trade_date=d,
                        symbol=symbol,
                        name=pos.name,
                        side="sell",
                        quantity=pos.quantity,
                        price=round(close, 4),
                        commission=round(comm, 2),
                        realized_pnl=round(realized, 2),
                        cost_price=round(pos.cost_price, 4),
                        reason="周度调仓：跌出目标池，按动量换出",
                    ))
                    del holdings[symbol]

                # 买入：目标池里当前未持有的，按 ranking 顺序补齐
                slots = max(0, target_n - len(holdings))
                if slots > 0 and cash > 0:
                    per_slot = cash / slots
                    for symbol in ranking:
                        if slots <= 0:
                            break
                        if symbol in holdings:
                            continue
                        price = price_at(symbol, d, "close")
                        if not price or price <= 0:
                            continue
                        qty = _round_lot(int(per_slot / price))
                        if qty < 100:
                            continue
                        amount = qty * price
                        comm = _buy_commission(amount)
                        if cash < amount + comm:
                            continue
                        cash -= amount + comm
                        holdings[symbol] = HoldingState(
                            symbol=symbol,
                            name=name_lookup.get(symbol, symbol),
                            quantity=qty,
                            cost_price=price,
                        )
                        trades.append(PendingTrade(
                            trade_date=d,
                            symbol=symbol,
                            name=name_lookup.get(symbol, symbol),
                            side="buy",
                            quantity=qty,
                            price=round(price, 4),
                            commission=round(comm, 2),
                            reason="周度调仓：进入动量前列，按目标配置买入",
                        ))
                        slots -= 1

            # 周一收盘后留一条复盘素材
            week_trades = [t for t in trades if t.trade_date == d]
            if week_trades:
                holding_value = sum(
                    (price_at(p.symbol, d, "close") or 0.0) * p.quantity
                    for p in holdings.values()
                )
                weekly_inputs.append(WeeklyReflectionInput(
                    week_end=d,
                    summary_context={
                        "mode": "weekly_summary",
                        "trade_count": len(week_trades),
                        "buy_count": sum(1 for t in week_trades if t.side == "buy"),
                        "sell_count": sum(1 for t in week_trades if t.side == "sell"),
                        "available_cash": round(cash, 2),
                        "holding_value": round(holding_value, 2),
                        "total_asset": round(cash + holding_value, 2),
                        "position_count": len(holdings),
                    },
                ))

    return ResearcherBackfillResult(
        researcher_id=researcher.id,
        researcher_name=researcher.name,
        trades=trades,
        final_positions=holdings,
        final_cash=cash,
        weekly_reflections=weekly_inputs,
    )


def replay_sentiment_ultrashort(
    *,
    researcher: Researcher,
    trade_dates: list[date],
    universe_bars: dict[str, list[HistoryBar]],
    initial_cash: float,
) -> ResearcherBackfillResult:
    """情绪超短合成回放：短持仓、高换手、止盈止损，区别于小市值周度轮动。"""
    if not trade_dates:
        return ResearcherBackfillResult(
            researcher_id=researcher.id,
            researcher_name=researcher.name,
            trades=[],
            final_positions={},
            final_cash=initial_cash,
            weekly_reflections=[],
        )

    config = researcher.strategy_config or {}
    max_positions = int(config.get("max_daily_new_positions_strong") or 3)
    max_hold_days = int(config.get("risk_control", {}).get("max_hold_days") or 3)
    stop_loss = float(config.get("risk_control", {}).get("stop_loss") or -0.05)
    take_profit_half = float(config.get("risk_control", {}).get("take_profit_half") or 0.10)
    take_profit_full = float(config.get("risk_control", {}).get("take_profit_full") or 0.15)

    cash = float(initial_cash)
    holdings: dict[str, HoldingState] = {}
    trades: list[PendingTrade] = []
    weekly_inputs: list[WeeklyReflectionInput] = []
    universe_meta = {symbol: bars for symbol, bars in universe_bars.items() if bars}
    name_lookup = {symbol: symbol for symbol in universe_meta}

    def bar_at(symbol: str, d: date) -> HistoryBar | None:
        bars = universe_meta.get(symbol)
        if not bars:
            return None
        d_iso = d.isoformat()
        for b in bars:
            if b.date == d_iso:
                return b
        return None

    def recent_strength(symbol: str, idx: int, window: int = 3) -> float | None:
        bars = universe_meta.get(symbol)
        if not bars:
            return None
        d_iso = trade_dates[idx].isoformat()
        series = [b for b in bars if b.date <= d_iso]
        if len(series) <= window:
            return None
        current = series[-1]
        previous = series[-1 - window]
        if previous.close <= 0:
            return None
        gap_score = max(0.0, (current.open - previous.close) / previous.close)
        momentum = (current.close - previous.close) / previous.close
        volume_score = min(current.amount / 1_000_000_000, 10.0) / 100
        return momentum + gap_score + volume_score

    def sell_position(symbol: str, d: date, price: float, reason: str) -> None:
        nonlocal cash
        pos = holdings.get(symbol)
        if pos is None:
            return
        amount = pos.quantity * price
        comm = _sell_commission(amount)
        realized = (price - pos.cost_price) * pos.quantity - comm
        cash += amount - comm
        trades.append(PendingTrade(
            trade_date=d,
            symbol=symbol,
            name=pos.name,
            side="sell",
            quantity=pos.quantity,
            price=round(price, 4),
            commission=round(comm, 2),
            realized_pnl=round(realized, 2),
            cost_price=round(pos.cost_price, 4),
            reason=reason,
        ))
        del holdings[symbol]

    for idx, d in enumerate(trade_dates):
        # 先处理持仓：超短 1-3 天内按止盈、止损、到期卖出。
        for symbol in list(holdings.keys()):
            pos = holdings[symbol]
            bar = bar_at(symbol, d)
            if not bar or pos.cost_price <= 0:
                continue
            high_ret = (bar.high - pos.cost_price) / pos.cost_price
            low_ret = (bar.low - pos.cost_price) / pos.cost_price
            hold_days = idx - pos.entry_idx
            if low_ret <= stop_loss:
                sell_position(symbol, d, max(bar.close, pos.cost_price * (1 + stop_loss)), "超短风控：跌破 5% 止损线")
            elif high_ret >= take_profit_full:
                sell_position(symbol, d, pos.cost_price * (1 + take_profit_full), "超短止盈：触及 15% 清仓线")
            elif high_ret >= take_profit_half and hold_days >= 1:
                sell_position(symbol, d, bar.close, "超短止盈：触及 10% 后次日兑现")
            elif hold_days >= max_hold_days:
                sell_position(symbol, d, bar.close, "超短纪律：持仓满 3 个交易日退出")

        # 再开新仓：每个交易日最多补到 3 只，按近 3 日强度挑选。
        slots = max(0, max_positions - len(holdings))
        if slots <= 0 or cash <= 20_000:
            continue
        candidates: list[tuple[str, float]] = []
        for symbol in universe_meta:
            if symbol in holdings:
                continue
            score = recent_strength(symbol, idx)
            bar = bar_at(symbol, d)
            if score is None or not bar or bar.close <= 0:
                continue
            if score <= 0.015:
                continue
            candidates.append((symbol, score))
        candidates.sort(key=lambda x: x[1], reverse=True)

        for symbol, score in candidates[:slots]:
            bar = bar_at(symbol, d)
            if not bar:
                continue
            budget = min(cash / max(1, slots), initial_cash * 0.18)
            qty = _round_lot(int(budget / bar.close))
            if qty < 100:
                continue
            amount = qty * bar.close
            comm = _buy_commission(amount)
            if cash < amount + comm:
                continue
            cash -= amount + comm
            holdings[symbol] = HoldingState(
                symbol=symbol,
                name=name_lookup.get(symbol, symbol),
                quantity=qty,
                cost_price=bar.close,
                entry_idx=idx,
            )
            trades.append(PendingTrade(
                trade_date=d,
                symbol=symbol,
                name=name_lookup.get(symbol, symbol),
                side="buy",
                quantity=qty,
                price=round(bar.close, 4),
                commission=round(comm, 2),
                reason=f"情绪超短：近 3 日强度靠前，分数 {score:.2%}",
            ))

        if d.weekday() == 4:
            holding_value = sum(
                (bar_at(p.symbol, d).close if bar_at(p.symbol, d) else p.cost_price) * p.quantity
                for p in holdings.values()
            )
            week_trades = [t for t in trades if t.trade_date >= d - timedelta(days=4) and t.trade_date <= d]
            if week_trades:
                weekly_inputs.append(WeeklyReflectionInput(
                    week_end=d,
                    summary_context={
                        "mode": "sentiment_weekly_summary",
                        "strategy_type": "sentiment_ultrashort",
                        "trade_count": len(week_trades),
                        "buy_count": sum(1 for t in week_trades if t.side == "buy"),
                        "sell_count": sum(1 for t in week_trades if t.side == "sell"),
                        "available_cash": round(cash, 2),
                        "holding_value": round(holding_value, 2),
                        "total_asset": round(cash + holding_value, 2),
                        "position_count": len(holdings),
                    },
                ))

    return ResearcherBackfillResult(
        researcher_id=researcher.id,
        researcher_name=researcher.name,
        trades=trades,
        final_positions=holdings,
        final_cash=cash,
        weekly_reflections=weekly_inputs,
    )


# ────────────────────────────────────────────────────────────
# DB 写入
# ────────────────────────────────────────────────────────────

async def fetch_active_researchers(
    session: AsyncSession, researcher_id: str | None
) -> list[Researcher]:
    stmt = select(Researcher).where(Researcher.strategy_config.isnot(None))
    if researcher_id:
        stmt = stmt.where(Researcher.id == researcher_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def fetch_account_for(
    session: AsyncSession, researcher_id: str
) -> TradingAccount | None:
    stmt = select(TradingAccount).where(TradingAccount.researcher_id == researcher_id)
    result = await session.execute(stmt)
    return result.scalars().first()


async def clear_window(
    session: AsyncSession, account_id: str, start_dt: datetime, end_dt: datetime
) -> tuple[int, int, int]:
    """删除目标账户在窗口内已有的 trade_records / trade_logs，并清空所有 positions。

    返回：(records_deleted, logs_deleted, positions_deleted)
    """
    rec_res = await session.execute(
        delete(TradeRecord).where(and_(
            TradeRecord.account_id == account_id,
            TradeRecord.created_at >= start_dt,
            TradeRecord.created_at < end_dt,
        ))
    )
    log_res = await session.execute(
        delete(TradeLog).where(and_(
            TradeLog.account_id == account_id,
            TradeLog.created_at >= start_dt,
            TradeLog.created_at < end_dt,
        ))
    )
    pos_res = await session.execute(
        delete(Position).where(Position.account_id == account_id)
    )
    return (rec_res.rowcount or 0, log_res.rowcount or 0, pos_res.rowcount or 0)


async def write_result(
    *,
    session: AsyncSession,
    researcher: Researcher,
    account: TradingAccount,
    result: ResearcherBackfillResult,
    final_close_prices: dict[str, float],
    skip_reflection: bool,
) -> None:
    """把 PendingTrade 列表落库 + 重建 positions + 更新账户。"""
    # 把同一天的 trade 用一条 trade-log 包起来，更接近真实日志体感
    trades_by_day: dict[date, list[tuple[str, PendingTrade]]] = defaultdict(list)
    for t in result.trades:
        # 时间戳：按交易日 09:31 + 序号 错开
        trade_id = f"trd_{uuid4().hex[:8]}"
        # 写 TradeRecord
        ts_idx = len(trades_by_day[t.trade_date])
        created_at = datetime.combine(
            t.trade_date,
            datetime.min.time().replace(hour=9, minute=31),
            tzinfo=SHANGHAI_TZ,
        ) + timedelta(seconds=ts_idx * 7)
        amount = t.price * t.quantity
        rec = TradeRecord(
            id=trade_id,
            account_id=account.id,
            symbol=t.symbol,
            name=t.name,
            side=t.side,
            quantity=t.quantity,
            price=float(t.price),
            commission=float(t.commission),
        )
        rec.created_at = created_at
        rec.updated_at = created_at
        session.add(rec)
        trades_by_day[t.trade_date].append((trade_id, t))

    # 每个交易日生成一条 log_type=trade 的日志（聚合当日所有成交）
    for d, items in trades_by_day.items():
        record_ids = [tid for tid, _ in items]
        log_created = datetime.combine(
            d,
            datetime.min.time().replace(hour=9, minute=31),
            tzinfo=SHANGHAI_TZ,
        )
        log = TradeLog(
            id=f"tl_{uuid4().hex[:8]}",
            account_id=account.id,
            log_type="trade",
            trade_record_ids=json.dumps(record_ids),
            title=f"{d.isoformat()} 调仓成交",
            content="",
        )
        log.created_at = log_created
        log.updated_at = log_created
        session.add(log)

    # 周度 AI 复盘日志（log_type=analysis）
    if not skip_reflection:
        for w in result.weekly_reflections:
            try:
                content = await _reflection_skill.build_trade_reflection(
                    researcher_name=researcher.name,
                    researcher_prompt=researcher.prompt,
                    trade_context=w.summary_context,
                )
            except Exception:
                logger.exception("[%s] 周度复盘 LLM 调用失败，回退模板", researcher.name)
                content = _reflection_skill.build_fallback_reflection(
                    researcher_name=researcher.name,
                    researcher_prompt=researcher.prompt,
                    trade_context={**w.summary_context, "side": "buy", "symbol": "周度", "name": "周度复盘"},
                )
            created = datetime.combine(
                w.week_end,
                datetime.min.time().replace(hour=15, minute=10),
                tzinfo=SHANGHAI_TZ,
            )
            log = TradeLog(
                id=f"tl_{uuid4().hex[:8]}",
                account_id=account.id,
                log_type="analysis",
                trade_record_ids="[]",
                title=f"{w.week_end.isoformat()} 周度复盘",
                content=content,
            )
            log.created_at = created
            log.updated_at = created
            session.add(log)

    # 重建 positions
    holding_value = 0.0
    for symbol, h in result.final_positions.items():
        last_close = final_close_prices.get(symbol, h.cost_price)
        pnl = (last_close - h.cost_price) * h.quantity
        holding_value += last_close * h.quantity
        session.add(Position(
            id=f"pos_{uuid4().hex[:8]}",
            account_id=account.id,
            symbol=h.symbol,
            name=h.name,
            quantity=h.quantity,
            cost_price=round(h.cost_price, 4),
            current_price=round(last_close, 4),
            pnl=round(pnl, 2),
        ))

    # 更新账户
    account.available_cash = round(result.final_cash, 2)
    account.holding_value = round(holding_value, 2)
    account.total_asset = round(result.final_cash + holding_value, 2)
    account.daily_pnl = 0.0  # 简化：本批补全不细算最后一日 PnL


# ────────────────────────────────────────────────────────────
# 主流程
# ────────────────────────────────────────────────────────────

async def run(
    *,
    days: int,
    researcher_id: str | None,
    commit: bool,
    skip_reflection: bool,
    keep_existing: bool,
) -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # 1) 确定回放窗口
    today = date.today()
    trade_dates = await run_sync(list_recent_trade_dates, today, days)
    if not trade_dates:
        logger.error("无法获取交易日历，退出")
        return 1
    start_d, end_d = trade_dates[0], trade_dates[-1]
    logger.info("回放窗口：%s ~ %s 共 %d 个交易日", start_d, end_d, len(trade_dates))

    async with session_factory() as session:
        researchers = await fetch_active_researchers(session, researcher_id)
        if not researchers:
            logger.error("没有任何带 strategy_config 的研究员")
            return 1
        logger.info("命中 %d 个研究员：%s", len(researchers),
                    ", ".join(f"{r.name}({r.id})" for r in researchers))

        # 2) 收集所有 universe 的并集，一次拉历史 K 线
        all_symbols: set[str] = set()
        researcher_universe: dict[str, list[tuple[str, str]]] = {}
        for r in researchers:
            uv = resolve_universe(r.strategy_config)
            researcher_universe[r.id] = uv
            for s, _n in uv:
                all_symbols.add(s)

        logger.info("拉取历史 K 线（%d 只 × %d 天，可能耗时）...", len(all_symbols), len(trade_dates))
        bars_map = await run_sync(
            get_stock_history_batch_for_backfill,
            sorted(all_symbols),
            start_d - timedelta(days=45),  # 多取 45 天给动量打底
            end_d,
        )
        # 给 universe 注入真实股票名
        # （HistoryBar 不带名字；直接用 universe 元信息映射）
        symbol_name: dict[str, str] = {}
        for r in researchers:
            for s, n in researcher_universe[r.id]:
                symbol_name.setdefault(s, n)

        # 3) 逐研究员回放
        results: list[ResearcherBackfillResult] = []
        for r in researchers:
            uv = researcher_universe[r.id]
            uv_bars = {s: bars_map.get(s, []) for s, _n in uv}
            if (r.strategy_config or {}).get("strategy_type") == "sentiment_ultrashort":
                res = replay_sentiment_ultrashort(
                    researcher=r,
                    trade_dates=trade_dates,
                    universe_bars=uv_bars,
                    initial_cash=1_000_000.0,
                )
            else:
                res = replay_one_researcher(
                    researcher=r,
                    trade_dates=trade_dates,
                    universe_bars=uv_bars,
                    initial_cash=1_000_000.0,
                )
            # 回填 name（replay_one_researcher 内部用了 symbol 占位）
            for symbol, h in res.final_positions.items():
                h.name = symbol_name.get(symbol, h.name)
            for t in res.trades:
                if not t.name or t.name == t.symbol:
                    t.name = symbol_name.get(t.symbol, t.symbol)
            results.append(res)
            logger.info(
                "[%s] 模拟成交 %d 笔（买 %d / 卖 %d），最终持仓 %d 只，可用资金 %.0f",
                r.name,
                len(res.trades),
                sum(1 for t in res.trades if t.side == "buy"),
                sum(1 for t in res.trades if t.side == "sell"),
                len(res.final_positions),
                res.final_cash,
            )

        # 4) Dry-run 输出 vs 真写入
        if not commit:
            print()
            print("=" * 78)
            print("DRY-RUN 摘要（未写库）。加 --commit 才会真正写入 DB。")
            print("=" * 78)
            for res in results:
                print(f"\n▶ {res.researcher_name} ({res.researcher_id})")
                print(f"  成交：{len(res.trades)} 笔  |  最终持仓：{len(res.final_positions)} 只  |  剩余资金：{res.final_cash:,.0f}")
                # 列前 10 笔
                for t in res.trades[:10]:
                    flag = "买入" if t.side == "buy" else "卖出"
                    pnl = f"  实现盈亏 {t.realized_pnl:+,.0f}" if t.realized_pnl is not None else ""
                    print(f"   {t.trade_date} {flag} {t.symbol} {t.name} {t.quantity}股 @ {t.price:.2f}{pnl}  | {t.reason}")
                if len(res.trades) > 10:
                    print(f"   ...（其余 {len(res.trades) - 10} 笔省略）")
            print()
            return 0

        # 5) 真写入
        empty_results = [
            res for res in results
            if not res.trades and not res.final_positions
        ]
        if empty_results:
            logger.error(
                "回放结果为空，已中止写库，避免清空模拟盘：%s",
                ", ".join(f"{res.researcher_name}({res.researcher_id})" for res in empty_results),
            )
            return 1

        async with session_factory() as wsession:
            for res in results:
                account = await fetch_account_for(wsession, res.researcher_id)
                if account is None:
                    logger.warning("[%s] 没有 trading_account，跳过", res.researcher_name)
                    continue

                if not keep_existing:
                    start_dt = datetime.combine(start_d, datetime.min.time(), tzinfo=SHANGHAI_TZ)
                    end_dt = datetime.combine(end_d + timedelta(days=1), datetime.min.time(), tzinfo=SHANGHAI_TZ)
                    rec_n, log_n, pos_n = await clear_window(wsession, account.id, start_dt, end_dt)
                    logger.info("[%s] 清理旧数据：trade %d / log %d / pos %d",
                                res.researcher_name, rec_n, log_n, pos_n)

                # 末日收盘价
                final_close: dict[str, float] = {}
                for symbol in res.final_positions:
                    bars = bars_map.get(symbol, [])
                    if not bars:
                        continue
                    end_iso = end_d.isoformat()
                    # 取 <= end_d 的最后一根
                    candidate = [b for b in bars if b.date <= end_iso]
                    if candidate:
                        final_close[symbol] = candidate[-1].close

                researcher = next(r for r in researchers if r.id == res.researcher_id)
                await write_result(
                    session=wsession,
                    researcher=researcher,
                    account=account,
                    result=res,
                    final_close_prices=final_close,
                    skip_reflection=skip_reflection,
                )
            await wsession.commit()
            logger.info("✓ 写入完成")

    await engine.dispose()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="模拟盘历史数据补全（合成式）")
    parser.add_argument("--days", type=int, default=30, help="回放最近 N 个交易日，默认 30")
    parser.add_argument("--researcher-id", type=str, default=None, help="只补指定研究员 id")
    parser.add_argument("--commit", action="store_true", help="真正写库；不带则 dry-run")
    parser.add_argument("--skip-reflection", action="store_true", help="跳过 LLM 周度复盘日志")
    parser.add_argument("--keep-existing", action="store_true", help="不清理 30 天内已有数据")
    args = parser.parse_args()

    return asyncio.run(run(
        days=args.days,
        researcher_id=args.researcher_id,
        commit=args.commit,
        skip_reflection=args.skip_reflection,
        keep_existing=args.keep_existing,
    ))


if __name__ == "__main__":
    sys.exit(main())
