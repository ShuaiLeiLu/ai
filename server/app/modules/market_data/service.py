from __future__ import annotations

from typing import Any

from app.integrations.jin10.client import Jin10McpClient, get_jin10_mcp_client
from app.modules.market_data.schemas import (
    CalendarItem,
    CursorPage,
    KlineData,
    NewsDetail,
    QuoteCode,
    QuoteSnapshot,
)


class UnknownQuoteCodeError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(f"Unsupported quote code: {code}")
        self.code = code


class MarketDataService:
    def __init__(self, client: Jin10McpClient | None = None) -> None:
        self.client = client or get_jin10_mcp_client()

    async def list_quote_codes(self) -> list[QuoteCode]:
        data = await self.client.read_resource("quote://codes")
        return [QuoteCode.model_validate(item) for item in data or []]

    async def get_quote(self, code: str) -> QuoteSnapshot:
        await self._ensure_quote_code(code)
        data = await self.client.call_tool("get_quote", {"code": code})
        return QuoteSnapshot.model_validate(data)

    async def get_kline(
        self,
        code: str,
        *,
        time: int | None = None,
        count: int | None = None,
    ) -> KlineData:
        await self._ensure_quote_code(code)
        arguments: dict[str, Any] = {"code": code}
        if time is not None:
            arguments["time"] = time
        if count is not None:
            arguments["count"] = count
        data = await self.client.call_tool("get_kline", arguments)
        return KlineData.model_validate(data)

    async def list_flash(self, *, cursor: str | None = None) -> CursorPage:
        return await self._cursor_page("list_flash", cursor=cursor)

    async def search_flash(self, keyword: str) -> CursorPage:
        data = await self.client.call_tool("search_flash", {"keyword": keyword})
        return self._page_from_data(data)

    async def list_news(self, *, cursor: str | None = None) -> CursorPage:
        return await self._cursor_page("list_news", cursor=cursor)

    async def search_news(self, keyword: str, *, cursor: str | None = None) -> CursorPage:
        arguments: dict[str, Any] = {"keyword": keyword}
        if cursor:
            arguments["cursor"] = cursor
        data = await self.client.call_tool("search_news", arguments)
        return self._page_from_data(data)

    async def get_news(self, news_id: str) -> NewsDetail:
        data = await self.client.call_tool("get_news", {"id": news_id})
        return NewsDetail.model_validate(data)

    async def list_calendar(self) -> list[CalendarItem]:
        data = await self.client.call_tool("list_calendar", {})
        return [CalendarItem.model_validate(item) for item in data or []]

    async def _ensure_quote_code(self, code: str) -> None:
        codes = await self.list_quote_codes()
        if not any(item.code == code for item in codes):
            raise UnknownQuoteCodeError(code)

    async def _cursor_page(self, tool_name: str, *, cursor: str | None) -> CursorPage:
        arguments = {"cursor": cursor} if cursor else {}
        data = await self.client.call_tool(tool_name, arguments)
        return self._page_from_data(data)

    @staticmethod
    def _page_from_data(data: Any) -> CursorPage:
        return CursorPage.model_validate(
            data or {"items": [], "next_cursor": None, "has_more": False},
        )
