from __future__ import annotations

from app.engine.strategies.smallcap_rotation import generate_target_pool_from_quotes


def _quote(symbol: str, name: str, change_pct: float, amount: float = 100_000_000.0) -> dict:
    return {
        "symbol": symbol,
        "name": name,
        "price": 10.0,
        "change_pct": change_pct,
        "amount": amount,
        "prev_close": 9.8,
        "volume": 10000,
        "circulating_market_cap": 0.0,
        "pe_ratio": 0.0,
        "pb_ratio": 0.0,
        "turnover_ratio": 0.0,
        "volume_ratio": 0.0,
        "change_pct_60d": change_pct,
        "change_pct_ytd": change_pct,
        "_source": "sina_basic",
    }


def test_basic_quote_fallback_selects_pool_without_bj_or_st() -> None:
    quotes = [
        _quote("920001", "北交样例", 20.0),
        _quote("600001", "*ST样例", 19.0),
        _quote("002001", "主板一", 8.0, 80_000_000),
        _quote("603001", "主板二", 7.0, 60_000_000),
        _quote("300001", "创业板", 9.0, 50_000_000),
    ]

    pool = generate_target_pool_from_quotes(
        {"stock_count": 3, "filters": {"exclude_st": True, "exclude_bj": True}},
        quotes,
    )

    assert [item["symbol"] for item in pool] == ["300001", "002001", "603001"]
