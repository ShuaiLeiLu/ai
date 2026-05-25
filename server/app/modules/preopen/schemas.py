from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from app.schemas.common import SchemaModel

NewsSentiment = Literal["bullish", "neutral", "bearish"]
NewsJumpType = Literal["news", "analysis"]
IndicatorKey = Literal[
    "highest_consecutive_limit_up",
    "limit_up_seal_ratio",
    "consecutive_limit_up_ratio",
    "turnover_growth",
    "nasdaq",
    "ftse_a50",
    # 主要指数（前缀 index_，code 来自新浪 / akshare）
    "index_sh000001",  # 上证指数
    "index_sz399001",  # 深证成指
    "index_sz399006",  # 创业板指
    "index_sh000300",  # 沪深300
    "index_sh000688",  # 科创50
    "index_hstech",    # 恒生科技
]
IndicatorDirection = Literal["up", "down", "flat"]
RiskTag = Literal["consecutive_limit_up", "abnormal_volatility", "st_risk", "high_turnover"]
AnomalyCategory = Literal["tail-session-move", "severe-volatility"]
TrendMetric = Literal[
    "daily_limit_up_count",
    "daily_limit_down_count",
    "consecutive_limit_up_count",
    "next_day_return_after_limit_up",
    "turnover_change",
]


class TradingCalendarHint(SchemaModel):
    trade_date: date
    is_trading_day: bool
    notice: str


class HotNewsItem(SchemaModel):
    news_id: str
    title: str
    summary: str
    source: str
    published_at: datetime
    heat: int
    sentiment: NewsSentiment
    symbols: list[str]
    jump_type: NewsJumpType
    jump_target: str


class AiDigest(SchemaModel):
    digest_id: str
    report_title: str | None = None
    headline: str
    interval_start: datetime
    interval_end: datetime
    generated_at: datetime
    sentiment: NewsSentiment
    key_points: list[str]
    report_sections: list["AiDigestSection"] = []
    news_drivers: list[str] = []
    opportunity_sectors: list[str] = []
    risk_sectors: list[str] = []
    intraday_watch: list[str] = []
    simulation_plan: list[str] = []


class AiDigestSection(SchemaModel):
    title: str
    paragraphs: list[str] = []
    bullets: list[str] = []
    table: list[dict[str, str]] = []


class MarketIndicator(SchemaModel):
    indicator: IndicatorKey
    label: str
    value: float
    unit: str
    direction: IndicatorDirection
    reference: str


class AnomalyItem(SchemaModel):
    symbol: str
    name: str
    category: AnomalyCategory
    change_pct: float
    turnover_ratio: float
    risk_tags: list[RiskTag]
    note: str
    risk_type: str | None = None
    risk_window: str | None = None
    is_new: bool = False


class AnomalyOverview(SchemaModel):
    calendar: TradingCalendarHint
    tail_session_moves: list[AnomalyItem]
    severe_volatility: list[AnomalyItem]


class TrendPoint(SchemaModel):
    trade_date: date
    value: float


class TrendSeries(SchemaModel):
    metric: TrendMetric
    label: str
    unit: str
    points: list[TrendPoint]


class TrendOverview(SchemaModel):
    calendar: TradingCalendarHint
    window_days: int
    series: list[TrendSeries]


class LimitUpLadderItem(SchemaModel):
    symbol: str
    name: str
    trade_date: date | None = None
    ladder_level: int
    change_pct: float | None = None
    first_seal_time: str
    final_seal_time: str
    reason: str
    risk_tags: list[RiskTag]


class IndustryBoardItem(SchemaModel):
    """行业板块涨跌条目。"""
    name: str                  # 板块名称
    change_pct: float          # 涨跌幅（%）
    total_amount: float        # 总成交额（亿元）
    net_inflow: float          # 净流入（亿元）
    rise_count: int            # 上涨家数
    fall_count: int            # 下跌家数
    leading_stock: str         # 领涨股
    leading_stock_pct: float   # 领涨股涨跌幅


class StockRankItem(SchemaModel):
    """涨跌榜个股条目。"""
    symbol: str                # 代码
    name: str                  # 名称
    change_pct: float          # 涨跌幅（%）
    price: float               # 最新价
    amount: float              # 成交额
    turnover_ratio: float      # 换手率
    industry: str              # 所属行业
    reason: str                # 入选理由（如"连板"、"60日新高"等）


class PreopenAllData(SchemaModel):
    """盘前速览聚合数据 —— 一次请求返回全部快照。"""
    hot_news: list[HotNewsItem]
    market_indicators: list[MarketIndicator]
    anomalies: AnomalyOverview | None
    trends: TrendOverview | None
    limit_up_ladder: list[LimitUpLadderItem]
    industry_boards: list[IndustryBoardItem]
    stock_rank_up: list[StockRankItem]
    stock_rank_down: list[StockRankItem]
