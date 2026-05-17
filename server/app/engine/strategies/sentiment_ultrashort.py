from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.paper_trading.executor import (
    do_buy,
    do_sell,
    invalidate_trading_cache,
    load_today_buy_quantities,
)
from app.engine.paper_trading.state import set_limit_up_symbols
from app.engine.strategies.market import fetch_realtime_quotes, safe_float
from app.integrations.akshare.client import (
    LimitUpStock,
    call_akshare_api,
    get_limit_down_pool,
    get_limit_up_pool,
    run_sync,
)
from app.models.researcher import Researcher
from app.models.trading import Position, TradeLog, TradingAccount

logger = logging.getLogger(__name__)

STRATEGY_TYPE = "sentiment_ultrashort"


@dataclass(slots=True)
class SentimentScore:
    total: float
    stage: str
    details: dict[str, float]


CandidateAudit = list[dict[str, str]]


def _audit_candidate(
    audit: CandidateAudit | None,
    *,
    stage: str,
    symbol: str,
    name: str,
    reason: str,
) -> None:
    if audit is None or len(audit) >= 80:
        return
    audit.append({
        "stage": stage,
        "symbol": symbol,
        "name": name,
        "reason": reason,
    })


def _linear_score(
    value: float,
    start: float,
    end: float,
    start_score: float,
    end_score: float,
) -> float:
    if start == end:
        return end_score
    ratio = (value - start) / (end - start)
    ratio = max(0.0, min(1.0, ratio))
    return round(start_score + ratio * (end_score - start_score), 4)


def _score_limit_up_count(count: int) -> float:
    if count < 15:
        return 0.0
    if count <= 30:
        return _linear_score(count, 15, 30, 5, 10)
    if count <= 60:
        return _linear_score(count, 30, 60, 10, 15)
    return 20.0


def _score_limit_down_count(count: int) -> float:
    if count > 20:
        return 0.0
    if count >= 10:
        return _linear_score(count, 20, 10, 5, 10)
    if count >= 5:
        return _linear_score(count, 10, 5, 10, 15)
    return 20.0


def _score_yesterday_premium(premium_pct: float) -> float:
    if premium_pct < -1:
        return 0.0
    if premium_pct <= 0:
        return _linear_score(premium_pct, -1, 0, 5, 10)
    if premium_pct <= 2:
        return _linear_score(premium_pct, 0, 2, 10, 15)
    return 20.0


def _score_height_breakthrough(breakthrough: int) -> float:
    if breakthrough <= 0:
        return 0.0
    if breakthrough == 1:
        return 5.0
    if breakthrough == 2:
        return 10.0
    return 15.0


def _score_break_rate(rate: float) -> float:
    if rate > 0.50:
        return 0.0
    if rate >= 0.30:
        return _linear_score(rate, 0.50, 0.30, 5, 10)
    return 15.0


def _score_mainline_count(count: int) -> float:
    if count < 3:
        return 0.0
    if count <= 5:
        return 5.0
    return 10.0


def _sentiment_stage(total_score: float) -> str:
    if total_score < 15:
        return "ice"
    if total_score < 30:
        return "retreat"
    if total_score < 55:
        return "launch"
    if total_score < 80:
        return "fermentation"
    return "climax"


def _sentiment_stage_label(stage: str) -> str:
    return {
        "ice": "冰点",
        "retreat": "退潮",
        "launch": "启动/弱修复",
        "fermentation": "发酵",
        "climax": "高潮",
    }.get(stage, stage)


def _calculate_sentiment_score(
    *,
    limit_up_count: int,
    limit_down_count: int,
    yesterday_premium_pct: float,
    height_breakthrough: int,
    break_rate: float,
    mainline_limit_up_count: int,
) -> SentimentScore:
    details = {
        "limit_up_count": _score_limit_up_count(limit_up_count),
        "limit_down_count": _score_limit_down_count(limit_down_count),
        "yesterday_premium": _score_yesterday_premium(yesterday_premium_pct),
        "height_breakthrough": _score_height_breakthrough(height_breakthrough),
        "break_rate": _score_break_rate(break_rate),
        "mainline_limit_up_count": _score_mainline_count(mainline_limit_up_count),
    }
    total = round(sum(details.values()), 2)
    return SentimentScore(total=total, stage=_sentiment_stage(total), details=details)


def _previous_trade_dates(anchor: date, count: int) -> list[date]:
    days: list[date] = []
    cursor = anchor - timedelta(days=1)
    while len(days) < count:
        if cursor.weekday() < 5:
            days.append(cursor)
        cursor -= timedelta(days=1)
    return days


def _is_main_board_symbol(symbol: str) -> bool:
    if len(symbol) != 6:
        return False
    if symbol.startswith(("300", "301", "688", "689", "4", "8")):
        return False
    return symbol.startswith(("000", "001", "002", "003", "600", "601", "603", "605"))


def _is_20cm_symbol(symbol: str) -> bool:
    return symbol.startswith(("300", "301", "688", "689"))


def _is_excluded_name(name: str) -> bool:
    upper = name.upper()
    return "ST" in upper or "*" in name or "退" in name


def _is_main_board_normal_stock(symbol: str, name: str) -> bool:
    return _is_main_board_symbol(symbol) and not _is_excluded_name(name)


def _quote_map(all_quotes: list[dict]) -> dict[str, dict]:
    return {q["symbol"]: q for q in all_quotes if q.get("symbol")}


def _text_value(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return "" if text.lower() == "nan" else text


def _normalize_stock_symbol(value: object) -> str:
    digits = "".join(ch for ch in _text_value(value) if ch.isdigit())
    if len(digits) < 6:
        return ""
    return digits[-6:]


def _market_cap_yuan(quote: dict | None) -> float:
    if not quote:
        return 0.0
    return safe_float(quote.get("circulating_market_cap"))


def _passes_low_position_filter(quote: dict | None, config: dict) -> bool:
    if not quote:
        return True
    threshold = config.get("filters", {}).get("low_position_percentile_1y")
    if threshold is None:
        return True
    for key in ("price_position_1y", "year_position_pct", "low_position_percentile_1y"):
        raw_value = quote.get(key)
        if raw_value is None:
            continue
        value = safe_float(raw_value, default=-1.0)
        if value < 0:
            continue
        if value > 1:
            value = value / 100
        return value <= float(threshold)
    return True


def _amount_yuan_from_limit_stock(stock: LimitUpStock, quote: dict | None) -> float:
    return stock.amount or safe_float(quote.get("amount") if quote else 0.0)


def _time_to_int(value: str) -> int:
    digits = "".join(ch for ch in value if ch.isdigit())
    if not digits:
        return 0
    if len(digits) <= 4:
        digits = digits.zfill(4) + "00"
    return int(digits[:6])


def _is_within_time_window(now: datetime, start: time, end: time) -> bool:
    return start <= now.time() <= end


def _industry_limit_counts(limit_up_pool: list[LimitUpStock]) -> Counter[str]:
    return Counter(s.industry or "未分类" for s in limit_up_pool)


def _fetch_industry_member_map(industry_names: list[str]) -> dict[str, str]:
    member_map: dict[str, str] = {}
    for industry in industry_names:
        try:
            df = call_akshare_api("stock_board_industry_cons_em", symbol=industry)
        except Exception:
            logger.exception("[情绪超短] 获取行业成分失败：%s", industry)
            continue
        for _, row in df.iterrows():
            symbol = _normalize_stock_symbol(row.get("代码"))
            if symbol:
                member_map.setdefault(symbol, industry)
    return member_map


def _enrich_quotes_with_mainline_industries(
    all_quotes: list[dict],
    today_limit_counts: Counter[str],
    config: dict,
) -> list[dict]:
    min_follow = int(
        config.get("topic_confirmation", {}).get("halfway_min_follow_limit_up", 2)
    )
    mainline_industries = [
        industry
        for industry, count in today_limit_counts.items()
        if industry and industry != "未分类" and count >= min_follow
    ]
    if not mainline_industries:
        return all_quotes

    industry_by_symbol = _fetch_industry_member_map(mainline_industries)
    if not industry_by_symbol:
        return all_quotes

    enriched: list[dict] = []
    for quote in all_quotes:
        symbol = _normalize_stock_symbol(quote.get("symbol"))
        industry = _text_value(quote.get("industry") or quote.get("所属行业"))
        if industry or not symbol:
            enriched.append(quote)
            continue
        mapped_industry = industry_by_symbol.get(symbol)
        if not mapped_industry:
            enriched.append(quote)
            continue
        enriched_quote = dict(quote)
        enriched_quote["industry"] = mapped_industry
        enriched.append(enriched_quote)
    return enriched


def _top_industry_limit_count(limit_up_pool: list[LimitUpStock]) -> int:
    return max(_industry_limit_counts(limit_up_pool).values(), default=0)


def _fetch_broken_board_count(trade_day: date) -> int:
    dt_str = trade_day.strftime("%Y%m%d")
    try:
        df = call_akshare_api("stock_zt_pool_zbgc_em", date=dt_str)
    except Exception:
        logger.exception("[情绪超短] 获取炸板池失败：%s", dt_str)
        return 0
    return len(df)


def _recent_limit_height(anchor: date, lookback_days: int) -> int:
    heights: list[int] = []
    for day in _previous_trade_dates(anchor, lookback_days):
        pool = get_limit_up_pool(day)
        heights.append(max((s.consecutive for s in pool), default=0))
    return max(heights, default=0)


def _yesterday_limit_premium_pct(
    all_quotes: list[dict],
    yesterday_pool: list[LimitUpStock],
) -> float:
    quotes = _quote_map(all_quotes)
    premiums: list[float] = []
    for stock in yesterday_pool:
        if not _is_main_board_normal_stock(stock.symbol, stock.name):
            continue
        q = quotes.get(stock.symbol)
        if not q:
            continue
        open_price = safe_float(q.get("open"))
        prev_close = safe_float(q.get("prev_close"))
        if open_price <= 0 or prev_close <= 0:
            continue
        premiums.append((open_price - prev_close) / prev_close * 100)
    if not premiums:
        return 0.0
    return round(sum(premiums) / len(premiums), 4)


def _build_sentiment_snapshot(
    all_quotes: list[dict],
    *,
    trade_day: date,
    lookback_days: int,
) -> tuple[SentimentScore, dict]:
    limit_up_pool = [
        s for s in get_limit_up_pool(trade_day)
        if _is_main_board_normal_stock(s.symbol, s.name)
    ]
    limit_down_pool = [
        s for s in get_limit_down_pool(trade_day)
        if _is_main_board_normal_stock(s.symbol, s.name)
    ]
    previous_day = _previous_trade_dates(trade_day, 1)[0]
    yesterday_pool = get_limit_up_pool(previous_day)

    recent_height = _recent_limit_height(trade_day, lookback_days)
    today_height = max((s.consecutive for s in limit_up_pool), default=0)
    broken_count = _fetch_broken_board_count(trade_day)
    if broken_count <= 0:
        broken_count = sum(1 for s in limit_up_pool if s.break_count > 0)
    attempted = len(limit_up_pool) + broken_count
    break_rate = broken_count / attempted if attempted > 0 else 0.0
    mainline_count = _top_industry_limit_count(limit_up_pool)
    premium = _yesterday_limit_premium_pct(all_quotes, yesterday_pool)

    score = _calculate_sentiment_score(
        limit_up_count=len(limit_up_pool),
        limit_down_count=len(limit_down_pool),
        yesterday_premium_pct=premium,
        height_breakthrough=today_height - recent_height,
        break_rate=break_rate,
        mainline_limit_up_count=mainline_count,
    )
    meta = {
        "limit_up_pool": limit_up_pool,
        "limit_down_pool": limit_down_pool,
        "yesterday_pool": yesterday_pool,
        "recent_height": recent_height,
        "today_height": today_height,
        "broken_count": broken_count,
        "break_rate": break_rate,
        "mainline_count": mainline_count,
        "yesterday_premium_pct": premium,
    }
    return score, meta


async def _fetch_realtime_quotes_async() -> list[dict]:
    return await run_sync(fetch_realtime_quotes)


async def _build_sentiment_snapshot_async(
    all_quotes: list[dict],
    *,
    trade_day: date,
    lookback_days: int,
) -> tuple[SentimentScore, dict]:
    return await run_sync(
        _build_sentiment_snapshot,
        all_quotes,
        trade_day=trade_day,
        lookback_days=lookback_days,
    )


async def _enrich_quotes_with_mainline_industries_async(
    all_quotes: list[dict],
    today_limit_counts: Counter[str],
    config: dict,
) -> list[dict]:
    return await run_sync(
        _enrich_quotes_with_mainline_industries,
        all_quotes,
        today_limit_counts,
        config,
    )


def _is_stock_pool_allowed(
    symbol: str,
    name: str,
    config: dict,
    *,
    allow_20cm: bool = False,
) -> bool:
    if _is_excluded_name(name):
        return False
    if symbol.startswith(("4", "8")):
        return False
    if _is_20cm_symbol(symbol):
        return allow_20cm and config.get("allow_20cm_front_runner", True)
    return _is_main_board_symbol(symbol)


def _passes_sentiment_liquidity_filters(
    *,
    symbol: str,
    name: str,
    quote: dict | None,
    turnover_ratio: float,
    amount: float,
    config: dict,
    allow_20cm: bool = False,
) -> bool:
    return _sentiment_liquidity_reject_reason(
        symbol=symbol,
        name=name,
        quote=quote,
        turnover_ratio=turnover_ratio,
        amount=amount,
        config=config,
        allow_20cm=allow_20cm,
    ) is None


def _sentiment_liquidity_reject_reason(
    *,
    symbol: str,
    name: str,
    quote: dict | None,
    turnover_ratio: float,
    amount: float,
    config: dict,
    allow_20cm: bool = False,
) -> str | None:
    if not _is_stock_pool_allowed(symbol, name, config, allow_20cm=allow_20cm):
        return "股票池过滤：ST/退市/北交所/20cm 或非主板不符合当前配置"
    filters = config.get("filters", {})
    cap = _market_cap_yuan(quote)
    min_cap = filters.get("min_circulating_market_cap", 2_000_000_000)
    max_cap = filters.get("max_circulating_market_cap", 15_000_000_000)
    if cap <= 0:
        return "流通市值未随行情落库/待接入，无法通过市值过滤"
    if cap < min_cap:
        return f"流通市值 {cap / 100_000_000:.1f} 亿低于下限 {min_cap / 100_000_000:.1f} 亿"
    if cap > max_cap:
        return f"流通市值 {cap / 100_000_000:.1f} 亿高于上限 {max_cap / 100_000_000:.1f} 亿"
    if amount < filters.get("min_daily_amount", 100_000_000):
        return f"成交额 {amount / 100_000_000:.1f} 亿低于下限"
    if turnover_ratio < filters.get("min_turnover_ratio", 5):
        return f"换手率 {turnover_ratio:.1f}% 低于下限"
    if turnover_ratio > filters.get("max_turnover_ratio", 25):
        return f"换手率 {turnover_ratio:.1f}% 高于上限"
    if not _passes_low_position_filter(quote, config):
        return "一年位置不够低，低位约束未通过"
    return None


def _target_from_limit_stock(
    stock: LimitUpStock,
    quote: dict | None,
    *,
    reason: str,
    signal_type: str,
    budget_multiplier: float = 1.0,
) -> dict:
    return {
        "symbol": stock.symbol,
        "name": stock.name,
        "price": stock.price,
        "prev_close": safe_float(quote.get("prev_close") if quote else 0.0),
        "volume": safe_float(quote.get("volume") if quote else 0.0),
        "reason": reason,
        "signal_type": signal_type,
        "budget_multiplier": budget_multiplier,
        "industry": stock.industry,
        "consecutive": stock.consecutive,
        "break_count": stock.break_count,
        "seal_amount": stock.seal_amount,
    }


def _sort_breakout_candidates(
    candidates: list[LimitUpStock],
    counts: Counter[str],
    quotes: dict[str, dict],
) -> list[LimitUpStock]:
    def sort_key(stock: LimitUpStock) -> tuple:
        quote = quotes.get(stock.symbol)
        cap = max(_market_cap_yuan(quote), 1.0)
        turnover_mid_distance = abs(stock.turnover_ratio - 15.0)
        seal_ratio = stock.seal_amount / cap if cap > 0 else 0.0
        return (
            -counts.get(stock.industry or "未分类", 0),
            _time_to_int(stock.first_seal_time),
            turnover_mid_distance,
            stock.break_count,
            -seal_ratio,
        )

    return sorted(candidates, key=sort_key)


def _select_breakout_limit_targets(
    *,
    limit_up_pool: list[LimitUpStock],
    quotes: dict[str, dict],
    recent_height: int,
    config: dict,
    audit: CandidateAudit | None = None,
) -> list[dict]:
    counts = _industry_limit_counts(limit_up_pool)
    filters = config.get("filters", {})
    seal_ratio_min = config.get("board_buy", {}).get("min_seal_amount_ratio", 0.01)
    latest_first_seal = config.get("board_buy", {}).get("latest_first_seal_time", "143000")
    latest_first_seal_int = _time_to_int(latest_first_seal)

    candidates: list[LimitUpStock] = []
    for stock in limit_up_pool:
        quote = quotes.get(stock.symbol)
        amount = _amount_yuan_from_limit_stock(stock, quote)
        if stock.consecutive <= recent_height:
            _audit_candidate(
                audit,
                stage="突破板",
                symbol=stock.symbol,
                name=stock.name,
                reason=f"连板高度 {stock.consecutive} 未突破近10日高度 {recent_height}",
            )
            continue
        if stock.break_count > filters.get("max_break_count", 2):
            _audit_candidate(
                audit,
                stage="突破板",
                symbol=stock.symbol,
                name=stock.name,
                reason=f"炸板次数 {stock.break_count} 超过上限",
            )
            continue
        if latest_first_seal_int and _time_to_int(stock.first_seal_time) > latest_first_seal_int:
            _audit_candidate(
                audit,
                stage="突破板",
                symbol=stock.symbol,
                name=stock.name,
                reason=f"首次封板时间 {stock.first_seal_time or '未落库'} 晚于 {latest_first_seal}",
            )
            continue
        reject_reason = _sentiment_liquidity_reject_reason(
            symbol=stock.symbol,
            name=stock.name,
            quote=quote,
            turnover_ratio=stock.turnover_ratio,
            amount=amount,
            config=config,
            allow_20cm=False,
        )
        if reject_reason:
            _audit_candidate(
                audit,
                stage="突破板",
                symbol=stock.symbol,
                name=stock.name,
                reason=reject_reason,
            )
            continue
        cap = _market_cap_yuan(quote)
        if cap <= 0 or stock.seal_amount < cap * seal_ratio_min:
            _audit_candidate(
                audit,
                stage="突破板",
                symbol=stock.symbol,
                name=stock.name,
                reason=f"封单金额不足市值 {seal_ratio_min:.1%} 要求",
            )
            continue
        candidates.append(stock)

    selected = _sort_breakout_candidates(candidates, counts, quotes)
    return [
        _target_from_limit_stock(
            stock,
            quotes.get(stock.symbol),
            reason=(
                f"冰点后突破近10日高度：{stock.consecutive}板 > "
                f"{recent_height}板，板上确认"
            ),
            signal_type="breakout_board",
        )
        for stock in selected[: config.get("max_daily_new_positions", 2)]
    ]


def _select_low_absorb_targets(
    *,
    all_quotes: list[dict],
    yesterday_pool: list[LimitUpStock],
    today_limit_counts: Counter[str],
    config: dict,
    now_shanghai: datetime,
    audit: CandidateAudit | None = None,
) -> list[dict]:
    low_cfg = config.get("low_absorb", {})
    low_start = time.fromisoformat(low_cfg.get("start", "09:30"))
    low_end = time.fromisoformat(low_cfg.get("end", "09:40"))
    if not _is_within_time_window(now_shanghai, low_start, low_end):
        _audit_candidate(
            audit,
            stage="低吸",
            symbol="-",
            name="时间窗",
            reason=f"当前时间 {now_shanghai.strftime('%H:%M')} 不在低吸窗口 {low_start.strftime('%H:%M')}-{low_end.strftime('%H:%M')}",
        )
        return []

    quotes = _quote_map(all_quotes)
    candidates: list[dict] = []
    for stock in yesterday_pool:
        q = quotes.get(stock.symbol)
        if not q:
            _audit_candidate(
                audit,
                stage="低吸",
                symbol=stock.symbol,
                name=stock.name,
                reason="昨日涨停标的今日行情未落库/待接入",
            )
            continue
        open_price = safe_float(q.get("open"))
        prev_close = safe_float(q.get("prev_close"))
        current_price = safe_float(q.get("price"))
        amount = safe_float(q.get("amount"))
        turnover = safe_float(q.get("turnover_ratio"))
        if open_price <= 0 or prev_close <= 0 or current_price <= 0:
            _audit_candidate(
                audit,
                stage="低吸",
                symbol=stock.symbol,
                name=stock.name,
                reason="开盘价/昨收/现价未随行情落库，无法判断承接",
            )
            continue
        open_pct = (open_price - prev_close) / prev_close * 100
        budget_multiplier = 1.0
        if low_cfg.get("min_open_pct", -3) <= open_pct <= low_cfg.get("max_open_pct", 1):
            pass
        elif 1 < open_pct <= low_cfg.get("observe_max_open_pct", 3):
            if current_price < open_price:
                _audit_candidate(
                    audit,
                    stage="低吸",
                    symbol=stock.symbol,
                    name=stock.name,
                    reason=f"高开 {open_pct:.2f}% 后跌破开盘价，承接不足",
                )
                continue
            if today_limit_counts.get(stock.industry or "未分类", 0) < 2:
                _audit_candidate(
                    audit,
                    stage="低吸",
                    symbol=stock.symbol,
                    name=stock.name,
                    reason=f"题材确认不足：{stock.industry or '未分类'} 今日涨停少于 2 家",
                )
                continue
            budget_multiplier = 0.5
        else:
            _audit_candidate(
                audit,
                stage="低吸",
                symbol=stock.symbol,
                name=stock.name,
                reason=f"开盘涨幅 {open_pct:.2f}% 不在低吸/观察区间",
            )
            continue
        reject_reason = _sentiment_liquidity_reject_reason(
            symbol=stock.symbol,
            name=stock.name,
            quote=q,
            turnover_ratio=turnover,
            amount=amount,
            config=config,
            allow_20cm=False,
        )
        if reject_reason:
            _audit_candidate(
                audit,
                stage="低吸",
                symbol=stock.symbol,
                name=stock.name,
                reason=reject_reason,
            )
            continue
        candidates.append({
            "symbol": stock.symbol,
            "name": stock.name,
            "price": current_price,
            "prev_close": prev_close,
            "volume": safe_float(q.get("volume")),
            "reason": f"破局龙次日低吸，开盘涨幅 {open_pct:.2f}%",
            "signal_type": "breakout_low_absorb",
            "budget_multiplier": budget_multiplier,
            "industry": stock.industry,
            "consecutive": stock.consecutive,
        })

    candidates.sort(key=lambda item: (-int(item.get("consecutive", 0)), item["symbol"]))
    return candidates[: config.get("max_daily_new_positions", 2)]


def _select_halfway_targets(
    *,
    all_quotes: list[dict],
    today_limit_counts: Counter[str],
    config: dict,
    now_shanghai: datetime,
    audit: CandidateAudit | None = None,
) -> list[dict]:
    half_cfg = config.get("halfway", {})
    half_start = time.fromisoformat(half_cfg.get("start", "09:40"))
    half_end = time.fromisoformat(half_cfg.get("end", "10:30"))
    if not _is_within_time_window(now_shanghai, half_start, half_end):
        _audit_candidate(
            audit,
            stage="半路",
            symbol="-",
            name="时间窗",
            reason=f"当前时间 {now_shanghai.strftime('%H:%M')} 不在半路窗口 {half_start.strftime('%H:%M')}-{half_end.strftime('%H:%M')}",
        )
        return []

    candidates: list[dict] = []
    min_follow = int(
        config.get("topic_confirmation", {}).get("halfway_min_follow_limit_up", 2)
    )
    for q in all_quotes:
        symbol = str(q.get("symbol", ""))
        name = str(q.get("name", ""))
        industry = str(q.get("industry", "") or q.get("所属行业", ""))
        change_pct = safe_float(q.get("change_pct"))
        if not industry or today_limit_counts.get(industry, 0) < min_follow:
            _audit_candidate(
                audit,
                stage="半路",
                symbol=symbol,
                name=name,
                reason=f"题材确认不足：{industry or '行业未随行情落库/待接入'} 涨停少于 {min_follow} 家",
            )
            continue
        if change_pct < half_cfg.get("min_change_pct", 5):
            _audit_candidate(
                audit,
                stage="半路",
                symbol=symbol,
                name=name,
                reason=f"涨幅 {change_pct:.2f}% 低于半路下限",
            )
            continue
        if change_pct > half_cfg.get("max_change_pct", 8):
            _audit_candidate(
                audit,
                stage="半路",
                symbol=symbol,
                name=name,
                reason=f"涨幅 {change_pct:.2f}% 高于半路上限，追高风险",
            )
            continue
        reject_reason = _sentiment_liquidity_reject_reason(
            symbol=symbol,
            name=name,
            quote=q,
            turnover_ratio=safe_float(q.get("turnover_ratio")),
            amount=safe_float(q.get("amount")),
            config=config,
            allow_20cm=False,
        )
        if reject_reason:
            _audit_candidate(
                audit,
                stage="半路",
                symbol=symbol,
                name=name,
                reason=reject_reason,
            )
            continue
        candidates.append({
            "symbol": symbol,
            "name": name,
            "price": safe_float(q.get("price")),
            "prev_close": safe_float(q.get("prev_close")),
            "volume": safe_float(q.get("volume")),
            "reason": f"发酵期主线补涨半路，涨幅 {change_pct:.2f}%",
            "signal_type": "mainline_halfway",
            "budget_multiplier": 1.0,
            "industry": industry,
        })

    candidates.sort(key=lambda item: (
        -today_limit_counts.get(str(item.get("industry", "")), 0),
        -safe_float(item.get("price")),
    ))
    return candidates[: config.get("max_daily_new_positions_strong", 3)]


def _gen_sentiment_daily_summary(
    *,
    score: SentimentScore,
    meta: dict,
    sell_count: int,
    buy_count: int,
    daily_pnl: float,
    total_asset: float,
    available_cash: float,
    hold_names: list[str],
    buy_audit: CandidateAudit | None = None,
) -> str:
    lines = ["## 超短情绪策略执行摘要\n"]
    lines.append(f"情绪分 {score.total:.1f}，阶段：{_sentiment_stage_label(score.stage)}。")
    lines.append(
        "涨停 {limit_up} 家，跌停 {limit_down} 家，昨日涨停开盘溢价 {premium:.2f}%，"
        "最高 {today_height} 板，近10日高度 {recent_height} 板，炸板率 {break_rate:.1%}。".format(
            limit_up=len(meta.get("limit_up_pool", [])),
            limit_down=len(meta.get("limit_down_pool", [])),
            premium=meta.get("yesterday_premium_pct", 0.0),
            today_height=meta.get("today_height", 0),
            recent_height=meta.get("recent_height", 0),
            break_rate=meta.get("break_rate", 0.0),
        )
    )
    lines.append(f"本次执行：卖出 {sell_count} 笔，买入 {buy_count} 笔。")
    lines.append(
        f"今日策略盈亏 {daily_pnl:,.2f} 元；账户总资产 {total_asset:,.2f} 元，"
        f"可用资金 {available_cash:,.2f} 元。"
    )
    if hold_names:
        lines.append(f"当前持仓 {len(hold_names)} 只：{'、'.join(hold_names)}。")
    else:
        lines.append("当前无持仓，等待下一次情绪确认。")
    if buy_count == 0:
        lines.append("## 为什么没买\n")
        if buy_audit:
            lines.append("本次没有强行下单，主要被以下条件过滤：")
            for item in buy_audit[:12]:
                symbol = item.get("symbol", "")
                name = item.get("name", "")
                display = name if symbol == "-" else f"{name}({symbol})"
                lines.append(f"- {item.get('stage', '候选')}｜{display}：{item.get('reason', '')}")
        else:
            lines.append("本次没有进入有效买点筛选，原因多半在情绪阶段、仓位上限或时间窗。")
    return "\n\n".join(lines)


def _half_sell_quantity(quantity: int) -> int:
    if quantity <= 100:
        return quantity
    half = int(quantity * 0.5 / 100) * 100
    return max(100, half)


def _stage_max_position_ratio(config: dict, stage: str) -> float:
    defaults = {
        "ice": 0.20,
        "retreat": 0.20,
        "launch": 0.40,
        "fermentation": 0.70,
        "climax": 0.30,
    }
    return float(config.get("position_limits", {}).get(stage, defaults.get(stage, 0.20)))


async def execute(session: AsyncSession, researcher: Researcher) -> int:
    from zoneinfo import ZoneInfo

    config = researcher.strategy_config or {}
    cost_config = config.get("cost", {})
    open_commission_rate = cost_config.get("open_commission", 0.0003)
    close_commission_rate = cost_config.get("close_commission", 0.0003)
    close_tax_rate = cost_config.get("close_tax", 0.001)
    min_commission = cost_config.get("min_commission", 5)
    risk_config = config.get("risk_control", {})
    stop_loss = float(risk_config.get("stop_loss", -0.05))
    take_profit_half = float(risk_config.get("take_profit_half", 0.10))
    take_profit_full = float(risk_config.get("take_profit_full", 0.15))
    max_hold_days = int(risk_config.get("max_hold_days", 3))
    lookback_days = int(config.get("emotion_score", {}).get("recent_height_days", 10))

    now_shanghai = datetime.now(tz=ZoneInfo("Asia/Shanghai"))
    trade_day = now_shanghai.date()

    acct_stmt = select(TradingAccount).where(TradingAccount.researcher_id == researcher.id)
    acct_result = await session.execute(acct_stmt)
    account = acct_result.scalar_one_or_none()
    if not account:
        logger.info("[情绪超短] %s 没有模拟账户，自动创建", researcher.name)
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

    all_quotes = await _fetch_realtime_quotes_async()
    score, meta = await _build_sentiment_snapshot_async(
        all_quotes,
        trade_day=trade_day,
        lookback_days=lookback_days,
    )
    limit_up_pool: list[LimitUpStock] = meta["limit_up_pool"]
    today_limit_counts = _industry_limit_counts(limit_up_pool)
    if score.stage == "fermentation":
        all_quotes = await _enrich_quotes_with_mainline_industries_async(
            all_quotes,
            today_limit_counts,
            config,
        )
    quotes = _quote_map(all_quotes)
    price_map = {symbol: safe_float(q.get("price")) for symbol, q in quotes.items()}

    high_limit_list: list[str] = []
    for symbol in current_positions:
        q = quotes.get(symbol)
        if q and safe_float(q.get("change_pct")) >= 9.8:
            high_limit_list.append(symbol)
    set_limit_up_symbols(researcher.id, high_limit_list)

    trade_count = 0
    daily_pnl = 0.0
    sell_count = 0
    buy_count = 0
    buy_audit: CandidateAudit = []

    for symbol, pos in list(current_positions.items()):
        q = quotes.get(symbol)
        cur_price = price_map.get(symbol) or float(pos.current_price)
        if cur_price <= 0:
            continue
        pnl_pct = (cur_price - float(pos.cost_price)) / float(pos.cost_price)
        sell_reason = ""
        sell_quantity: int | None = None

        if pnl_pct <= stop_loss:
            sell_reason = f"触发超短硬止损（{pnl_pct:.1%} <= {stop_loss:.0%}）"
        elif pnl_pct >= take_profit_full:
            sell_reason = f"达到全止盈线（{pnl_pct:.1%} >= {take_profit_full:.0%}）"
        elif pnl_pct >= take_profit_half and symbol not in high_limit_list:
            sell_quantity = _half_sell_quantity(int(pos.quantity))
            sell_reason = f"达到分批止盈线（{pnl_pct:.1%} >= {take_profit_half:.0%}）"
        elif score.stage in {"retreat", "climax"} and symbol not in high_limit_list:
            sell_reason = f"情绪进入{_sentiment_stage_label(score.stage)}，非涨停持仓降风险"
        elif pos.created_at:
            now_for_diff = now_shanghai
            if pos.created_at.tzinfo is None:
                now_for_diff = now_shanghai.replace(tzinfo=None)
            held_days = (now_for_diff - pos.created_at).days
            if held_days >= max_hold_days and symbol not in high_limit_list:
                sell_reason = f"持仓超过 {max_hold_days} 个交易日，超短不恋战"

        if sell_reason:
            sc, pnl = await do_sell(
                session,
                researcher,
                account,
                pos,
                cur_price,
                q,
                close_commission_rate,
                close_tax_rate,
                min_commission,
                sell_reason,
                quantity=sell_quantity,
            )
            trade_count += sc
            sell_count += sc
            daily_pnl += pnl
            if sc > 0 and int(pos.quantity) <= 0:
                current_positions.pop(symbol, None)

    max_total_ratio = _stage_max_position_ratio(config, score.stage)
    max_single_ratio = float(config.get("max_single_position_ratio", 0.20))
    max_20cm_ratio = float(config.get("max_20cm_position_ratio", 0.15))
    max_daily_new = int(config.get("max_daily_new_positions", 2))
    if score.stage == "fermentation":
        max_daily_new = int(config.get("max_daily_new_positions_strong", 3))

    today_buys = await load_today_buy_quantities(session, account.id)
    remaining_new_orders = max(0, max_daily_new - len(today_buys))
    current_exposure = sum(
        float(p.current_price) * int(p.quantity)
        for p in current_positions.values()
    )
    max_exposure = float(account.total_asset) * max_total_ratio
    exposure_budget = max(0.0, max_exposure - current_exposure)

    buy_targets: list[dict] = []
    if remaining_new_orders <= 0:
        _audit_candidate(
            buy_audit,
            stage="仓位约束",
            symbol="-",
            name="新开仓名额",
            reason="今日新开仓名额已用完",
        )
    elif exposure_budget <= 1000:
        _audit_candidate(
            buy_audit,
            stage="仓位约束",
            symbol="-",
            name="情绪仓位",
            reason=f"当前情绪阶段仓位预算仅 {exposure_budget:,.0f} 元，不足下单",
        )
    elif score.stage not in {"ice", "launch", "fermentation"}:
        _audit_candidate(
            buy_audit,
            stage="情绪过滤",
            symbol="-",
            name=_sentiment_stage_label(score.stage),
            reason=f"当前阶段为{_sentiment_stage_label(score.stage)}，策略配置不允许新开仓",
        )
    else:
        if score.stage in {"ice", "launch"}:
            buy_targets.extend(
                _select_low_absorb_targets(
                    all_quotes=all_quotes,
                    yesterday_pool=meta["yesterday_pool"],
                    today_limit_counts=today_limit_counts,
                    config=config,
                    now_shanghai=now_shanghai,
                    audit=buy_audit,
                )
            )
            buy_targets.extend(
                _select_breakout_limit_targets(
                    limit_up_pool=limit_up_pool,
                    quotes=quotes,
                    recent_height=int(meta["recent_height"]),
                    config=config,
                    audit=buy_audit,
                )
            )
        elif score.stage == "fermentation":
            buy_targets.extend(
                _select_halfway_targets(
                    all_quotes=all_quotes,
                    today_limit_counts=today_limit_counts,
                    config=config,
                    now_shanghai=now_shanghai,
                    audit=buy_audit,
                )
            )

    seen_targets: set[str] = set()
    for target in buy_targets:
        if buy_count >= remaining_new_orders:
            break
        symbol = target["symbol"]
        if symbol in current_positions:
            _audit_candidate(
                buy_audit,
                stage="下单过滤",
                symbol=symbol,
                name=str(target.get("name", "")),
                reason="账户已持有该标的，不重复开仓",
            )
            continue
        if symbol in today_buys:
            _audit_candidate(
                buy_audit,
                stage="下单过滤",
                symbol=symbol,
                name=str(target.get("name", "")),
                reason="今日已经买过该标的，避免重复加仓",
            )
            continue
        if symbol in seen_targets:
            _audit_candidate(
                buy_audit,
                stage="下单过滤",
                symbol=symbol,
                name=str(target.get("name", "")),
                reason="多个模式重复命中，已保留第一次候选",
            )
            continue
        seen_targets.add(symbol)
        single_ratio = max_20cm_ratio if _is_20cm_symbol(symbol) else max_single_ratio
        per_trade_budget = min(
            float(account.total_asset) * single_ratio,
            float(account.available_cash),
            exposure_budget,
        )
        per_trade_budget *= float(target.get("budget_multiplier", 1.0))
        if per_trade_budget < 1000:
            _audit_candidate(
                buy_audit,
                stage="下单过滤",
                symbol=symbol,
                name=str(target.get("name", "")),
                reason=f"可用下单预算仅 {per_trade_budget:,.0f} 元，不足最小下单金额",
            )
            continue
        bc, pnl = await do_buy(
            session,
            researcher,
            account,
            target,
            per_trade_budget,
            open_commission_rate,
            min_commission,
        )
        trade_count += bc
        buy_count += bc
        daily_pnl += pnl
        if bc > 0:
            exposure_budget = max(0.0, exposure_budget - per_trade_budget)

    for symbol, pos in current_positions.items():
        new_price = price_map.get(symbol) or float(pos.current_price)
        old_pnl = float(pos.pnl)
        pos.current_price = new_price
        pos.pnl = round((new_price - float(pos.cost_price)) * int(pos.quantity), 2)
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
            title="超短情绪策略执行摘要",
            content=_gen_sentiment_daily_summary(
                score=score,
                meta=meta,
                sell_count=sell_count,
                buy_count=buy_count,
                daily_pnl=daily_pnl,
                total_asset=account.total_asset,
                available_cash=account.available_cash,
                hold_names=[p.name for p in all_positions],
                buy_audit=buy_audit,
            ),
        )
    )

    await session.commit()
    invalidate_trading_cache(account, researcher.id)
    logger.info(
        "[情绪超短] %s 执行完成：情绪 %.1f/%s，成交 %d 笔",
        researcher.name,
        score.total,
        _sentiment_stage_label(score.stage),
        trade_count,
    )
    return trade_count


async def execute_intraday(session: AsyncSession, researcher: Researcher) -> int:
    return await execute(session, researcher)
