from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import SchemaModel

NewsCategory = Literal["flash", "announcement", "report"]
NewsFeedCategory = Literal["all", "flash", "announcement", "report"]
NewsSentiment = Literal["bullish", "neutral", "bearish"]
InterpretationType = Literal["event", "theme", "macro", "stock"]
AiPanelKey = Literal["24h_digest", "hotspot_tracking", "macro_impact", "stock_interpretation"]


class NewsStockRelation(SchemaModel):
    stock_code: str
    stock_name: str


class NewsThemeRelation(SchemaModel):
    theme_name: str


class NewsAiInterpretation(SchemaModel):
    interpretation_id: str
    interpretation_type: InterpretationType
    content: str
    confidence: float


class NewsAnalysisItem(SchemaModel):
    news_id: str
    category: NewsCategory
    source: str
    title: str
    summary: str
    content: str
    importance: int
    is_important: bool
    publish_time: datetime
    stock_relations: list[NewsStockRelation] = Field(default_factory=list)
    theme_relations: list[NewsThemeRelation] = Field(default_factory=list)
    ai_interpretations: list[NewsAiInterpretation] = Field(default_factory=list)


class NewsAiPanel(SchemaModel):
    panel_key: AiPanelKey
    title: str
    summary: str
    highlights: list[str]
    confidence: float
    updated_at: datetime


class HotStockTag(SchemaModel):
    stock_code: str
    stock_name: str
    heat: int
    label: str


class HotNewsRankItem(SchemaModel):
    rank: int
    news_id: str
    title: str
    source: str
    publish_time: datetime
    category: NewsCategory
    heat_score: int


class SentimentDistribution(SchemaModel):
    bullish: int = 0
    neutral: int = 0
    bearish: int = 0


class StockNewsSummary(SchemaModel):
    stock_code: str
    stock_name: str
    conclusion: str
    related_news_count: int
    sentiment_distribution: SentimentDistribution
    related_themes: list[str]
    avg_confidence: float
    latest_publish_time: datetime | None = None


class NewsAnalysisAllData(SchemaModel):
    """资讯分析聚合数据 —— 一次请求返回全部（不含 AI 面板，AI 面板由用户点击触发）。"""
    feed: list[NewsAnalysisItem]
    hot_stocks: list[HotStockTag]
    hot_news: list[HotNewsRankItem]
