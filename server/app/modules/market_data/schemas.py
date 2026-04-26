from __future__ import annotations

from typing import Any

from app.schemas.common import SchemaModel


class QuoteCode(SchemaModel):
    code: str
    name: str


class QuoteSnapshot(SchemaModel):
    code: str
    name: str | None = None
    time: str | None = None
    open: str | None = None
    close: str | None = None
    high: str | None = None
    low: str | None = None
    volume: int | float | str | None = None
    ups_price: str | None = None
    ups_percent: str | None = None


class KlineItem(SchemaModel):
    close: str | None = None
    high: str | None = None
    low: str | None = None
    open: str | None = None
    time: int | str | None = None
    volume: int | float | str | None = None


class KlineData(SchemaModel):
    code: str
    name: str | None = None
    klines: list[KlineItem]


class CursorPage(SchemaModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None
    has_more: bool = False


class NewsDetail(SchemaModel):
    id: str
    title: str | None = None
    introduction: str | None = None
    time: str | None = None
    url: str | None = None
    content: str | None = None


class CalendarItem(SchemaModel):
    pub_time: str | None = None
    star: int | None = None
    title: str | None = None
    previous: str | None = None
    consensus: str | None = None
    actual: str | None = None
    revised: str | None = None
    affect_txt: str | None = None

