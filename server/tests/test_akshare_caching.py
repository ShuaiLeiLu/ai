from __future__ import annotations

from datetime import date

import pandas as pd
from app.engine.strategies import market
from app.integrations.akshare import client as akshare_client


def test_historical_limit_up_pool_uses_long_lived_cache(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    def fake_call(api_name: str, **kwargs):
        calls.append((api_name, kwargs["date"]))
        return pd.DataFrame([
            {
                "代码": "600001",
                "名称": "测试股",
                "涨跌幅": 10.0,
                "最新价": 10.0,
                "成交额": 100000000,
                "换手率": 8,
                "封板资金": 50000000,
                "首次封板时间": "09:35:00",
                "最后封板时间": "09:35:00",
                "炸板次数": 0,
                "连板数": 2,
                "所属行业": "测试",
            }
        ])

    monkeypatch.setattr(akshare_client, "call_akshare_api", fake_call)
    akshare_client.invalidate_cache("limit_up:")

    first = akshare_client.get_limit_up_pool(date(2026, 5, 22))
    second = akshare_client.get_limit_up_pool(date(2026, 5, 22))

    assert len(first) == 1
    assert second == first
    assert calls == [("stock_zt_pool_em", "20260522")]


def test_failed_limit_up_pool_uses_short_negative_cache(monkeypatch) -> None:
    calls: list[str] = []

    def fake_call(api_name: str, **kwargs):
        calls.append(kwargs["date"])
        raise TimeoutError("upstream timeout")

    monkeypatch.setattr(akshare_client, "call_akshare_api", fake_call)
    akshare_client.invalidate_cache("limit_up:")

    first = akshare_client.get_limit_up_pool(date(2026, 5, 22))
    second = akshare_client.get_limit_up_pool(date(2026, 5, 22))

    assert first == []
    assert second == []
    assert calls == ["20260522"]


def test_realtime_quotes_are_cached_for_strategy_reuse(monkeypatch) -> None:
    calls: list[str] = []

    def fake_call(api_name: str):
        calls.append(api_name)
        return pd.DataFrame([
            {
                "代码": "600001",
                "名称": "测试股",
                "最新价": 10.0,
                "涨跌幅": 1.0,
                "成交额": 100000000,
                "今开": 9.9,
                "昨收": 9.8,
                "成交量": 10000,
                "流通市值": 1000000000,
                "市盈率-动态": 10,
                "市净率": 1,
                "换手率": 2,
                "量比": 1,
                "60日涨跌幅": 5,
                "年初至今涨跌幅": 6,
            }
        ])

    monkeypatch.setattr(market, "call_akshare_api", fake_call)
    market.invalidate_realtime_quotes_cache()

    first = market.fetch_realtime_quotes()
    second = market.fetch_realtime_quotes()

    assert first == second
    assert calls == ["stock_zh_a_spot_em"]
