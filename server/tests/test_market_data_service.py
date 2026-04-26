from __future__ import annotations

import pytest
from app.modules.market_data.service import MarketDataService, UnknownQuoteCodeError


class FakeJin10Client:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def read_resource(self, uri: str) -> list[dict]:
        assert uri == "quote://codes"
        return [{"code": "XAUUSD", "name": "现货黄金"}, {"code": "USOIL", "name": "WTI原油"}]

    async def call_tool(self, name: str, arguments: dict | None = None) -> object:
        self.calls.append((name, arguments or {}))
        if name == "get_quote":
            return {"code": "XAUUSD", "name": "现货黄金", "close": "4708.37"}
        if name == "get_kline":
            return {
                "code": "USOIL",
                "name": "WTI原油",
                "klines": [{"time": 1777064040, "close": "70.1"}],
            }
        if name == "list_flash":
            return {
                "items": [{"content": "快讯", "time": "2026-04-25T21:21:52+08:00"}],
                "has_more": True,
                "next_cursor": "c2",
            }
        raise AssertionError(f"unexpected tool {name}")


@pytest.mark.asyncio
async def test_quote_validates_code_before_calling_quote_tool() -> None:
    client = FakeJin10Client()
    service = MarketDataService(client=client)  # type: ignore[arg-type]

    quote = await service.get_quote("XAUUSD")

    assert quote.code == "XAUUSD"
    assert quote.close == "4708.37"
    assert client.calls == [("get_quote", {"code": "XAUUSD"})]


@pytest.mark.asyncio
async def test_quote_rejects_unknown_code_before_calling_tool() -> None:
    client = FakeJin10Client()
    service = MarketDataService(client=client)  # type: ignore[arg-type]

    with pytest.raises(UnknownQuoteCodeError):
        await service.get_quote("BAD")

    assert client.calls == []


@pytest.mark.asyncio
async def test_kline_uses_declared_arguments_only() -> None:
    client = FakeJin10Client()
    service = MarketDataService(client=client)  # type: ignore[arg-type]

    data = await service.get_kline("USOIL", time=1777060000, count=5)

    assert data.code == "USOIL"
    assert data.klines[0].close == "70.1"
    assert client.calls == [("get_kline", {"code": "USOIL", "time": 1777060000, "count": 5})]


@pytest.mark.asyncio
async def test_list_flash_preserves_cursor_pagination_fields() -> None:
    client = FakeJin10Client()
    service = MarketDataService(client=client)  # type: ignore[arg-type]

    page = await service.list_flash(cursor="c1")

    assert page.has_more is True
    assert page.next_cursor == "c2"
    assert page.items[0]["content"] == "快讯"
    assert client.calls == [("list_flash", {"cursor": "c1"})]
