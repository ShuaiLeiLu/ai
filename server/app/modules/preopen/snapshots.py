"""Preopen dashboard snapshot definitions."""
from __future__ import annotations

from datetime import date

from pydantic import TypeAdapter

from app.modules.preopen.schemas import (
    AnomalyOverview,
    HotNewsItem,
    IndustryBoardItem,
    LimitUpLadderItem,
    MarketIndicator,
    StockRankItem,
    TradingCalendarHint,
    TrendOverview,
)
from app.modules.preopen.snapshot_cache import SnapshotSpec


def _calendar_hint() -> TradingCalendarHint:
    today = date.today()
    return TradingCalendarHint(
        trade_date=today,
        is_trading_day=today.weekday() < 5,
        notice="非交易日展示最近交易日快照" if today.weekday() >= 5 else "盘前快照数据",
    )


def empty_anomalies() -> AnomalyOverview:
    return AnomalyOverview(
        calendar=_calendar_hint(),
        tail_session_moves=[],
        severe_volatility=[],
    )


def empty_trends() -> TrendOverview:
    return TrendOverview(
        calendar=_calendar_hint(),
        window_days=15,
        series=[],
    )


HOT_NEWS = SnapshotSpec[list[HotNewsItem]](
    name="hot-news",
    adapter=TypeAdapter(list[HotNewsItem]),
    empty_factory=list,
)
MARKET_INDICATORS = SnapshotSpec[list[MarketIndicator]](
    name="market-indicators",
    adapter=TypeAdapter(list[MarketIndicator]),
    empty_factory=list,
)
STOCK_RANK_UP = SnapshotSpec[list[StockRankItem]](
    name="stock-rank:up",
    adapter=TypeAdapter(list[StockRankItem]),
    empty_factory=list,
)
STOCK_RANK_DOWN = SnapshotSpec[list[StockRankItem]](
    name="stock-rank:down",
    adapter=TypeAdapter(list[StockRankItem]),
    empty_factory=list,
)
INDUSTRY_BOARDS = SnapshotSpec[list[IndustryBoardItem]](
    name="industry-boards",
    adapter=TypeAdapter(list[IndustryBoardItem]),
    empty_factory=list,
)
LIMIT_UP_LADDER = SnapshotSpec[list[LimitUpLadderItem]](
    name="limit-up-ladder",
    adapter=TypeAdapter(list[LimitUpLadderItem]),
    empty_factory=list,
)
ANOMALIES = SnapshotSpec[AnomalyOverview](
    name="anomalies",
    adapter=TypeAdapter(AnomalyOverview),
    empty_factory=empty_anomalies,
)
TRENDS = SnapshotSpec[TrendOverview](
    name="trends",
    adapter=TypeAdapter(TrendOverview),
    empty_factory=empty_trends,
)
