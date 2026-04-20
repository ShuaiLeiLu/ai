from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.common import SchemaModel

NewsCategory = Literal["flash", "announcement", "report"]
Sentiment = Literal["positive", "neutral", "negative"]


class NewsItem(SchemaModel):
    news_id: str
    title: str
    summary: str
    category: NewsCategory
    sentiment: Sentiment
    source: str
    symbols: list[str]
    importance: int
    published_at: datetime


class NewsDigest(SchemaModel):
    digest_id: str
    headline: str
    key_points: list[str]
    generated_at: datetime
