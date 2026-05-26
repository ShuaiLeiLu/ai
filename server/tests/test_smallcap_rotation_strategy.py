from __future__ import annotations

from datetime import date

import pytest
from app.engine.strategies import smallcap_rotation
from app.engine.strategies.smallcap_rotation import (
    generate_target_pool_from_quotes,
    get_stock_list,
)


def _stock(
    symbol: str,
    *,
    cap: float,
    sales: float,
    ms: float,
    peg: float,
    turnover_volatility: float = 1.0,
    eps: float = 1.0,
    price: float = 10.0,
    prev_close: float = 9.8,
    recent_limit_up: bool = False,
) -> dict:
    return {
        "symbol": symbol,
        "name": f"股票{symbol}",
        "price": price,
        "prev_close": prev_close,
        "volume": 10000,
        "amount": 100_000_000,
        "circulating_market_cap": cap,
        "eps": eps,
        "sales_growth": sales,
        "operating_revenue_growth_rate": ms,
        "total_profit_growth_rate": ms,
        "net_profit_growth_rate": ms,
        "earnings_growth": ms,
        "PEG": peg,
        "turnover_volatility": turnover_volatility,
        "start_date": "2020-01-01",
        "paused": False,
        "recent_limit_up": recent_limit_up,
    }


def _universe() -> list[dict]:
    stocks: list[dict] = []
    for index in range(40):
        stocks.append(
            _stock(
                f"000{index:03d}",
                cap=10_000_000_000 + index * 100_000_000,
                sales=100 - index,
                ms=100 - index,
                peg=1 + index,
                turnover_volatility=index,
            )
        )
    stocks.append(_stock("688001", cap=1, sales=999, ms=999, peg=0.1))
    stocks.append(_stock("000999", cap=1, sales=-999, ms=-999, peg=999, eps=-1))
    stocks.append(_stock("001999", cap=1, sales=-999, ms=-999, peg=999, price=10, prev_close=9.09))
    return stocks


def test_get_stock_list_uses_original_sg_ms_peg_factors() -> None:
    sg_list, ms_list, peg_list = get_stock_list(
        {"filters": {"exclude_kcb": True, "exclude_new_days": 375}},
        _universe(),
        as_of=date(2026, 5, 25),
    )

    assert [item["symbol"] for item in sg_list[:2]] == ["000000", "000001"]
    assert [item["symbol"] for item in ms_list[:2]] == ["000000", "000001"]
    assert [item["symbol"] for item in peg_list[:2]] == ["000000", "000001"]
    assert "688001" not in {item["symbol"] for item in sg_list + ms_list + peg_list}
    assert "000999" not in {item["symbol"] for item in sg_list + ms_list + peg_list}


def test_target_pool_sorts_union_by_circulating_market_cap_and_blacklist_intersection() -> None:
    universe = _universe()
    universe[0]["recent_limit_up"] = True
    universe[1]["recent_limit_up"] = False

    pool = generate_target_pool_from_quotes(
        {"stock_count": 3, "filters": {"exclude_new_days": 375}},
        universe,
        blacklist={"000000", "000001"},
        as_of=date(2026, 5, 25),
    )

    assert [item["symbol"] for item in pool] == ["000001", "000002", "000003"]


def test_missing_original_factor_fields_do_not_fall_back_to_momentum() -> None:
    quotes = [
        {
            "symbol": "600519",
            "name": "贵州茅台",
            "price": 1500,
            "prev_close": 1490,
            "volume": 10000,
            "amount": 2_000_000_000,
            "circulating_market_cap": 1_800_000_000_000,
            "change_pct": 9.0,
            "change_pct_ytd": 50.0,
        }
    ]

    pool = generate_target_pool_from_quotes({"stock_count": 10}, quotes, as_of=date(2026, 5, 25))

    assert pool == []


@pytest.mark.asyncio
async def test_adjustment_marker_is_set_only_after_successful_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    researcher = type(
        "Researcher",
        (),
        {
            "id": "r_marker",
            "name": "标记测试",
            "owner_id": "u_demo",
            "strategy_config": {"stock_count": 1},
        },
    )()
    account = type(
        "Account",
        (),
        {
            "id": "acct_marker",
            "available_cash": 1_000_000.0,
            "total_asset": 1_000_000.0,
            "holding_value": 0.0,
            "daily_pnl": 0.0,
        },
    )()
    session = object()

    async def fake_load_account(_session, _researcher):
        return account

    async def fake_load_positions(_session, _account_id):
        return {}

    async def fake_fetch_quotes():
        return [_stock("000001", cap=1_000_000_000, sales=20, ms=20, peg=1)]

    async def fail_commit(*_args, **_kwargs):
        raise TimeoutError("commit never reached")

    monkeypatch.setattr(smallcap_rotation, "_last_adjustment_date", {})
    monkeypatch.setattr(smallcap_rotation, "_hold_history", smallcap_rotation.defaultdict(list))
    monkeypatch.setattr(smallcap_rotation, "_not_buy_again", smallcap_rotation.defaultdict(set))
    monkeypatch.setattr(smallcap_rotation, "_load_account", fake_load_account)
    monkeypatch.setattr(smallcap_rotation, "_load_positions", fake_load_positions)
    monkeypatch.setattr(smallcap_rotation, "_fetch_realtime_quotes_async", fake_fetch_quotes)
    monkeypatch.setattr(smallcap_rotation, "_mark_to_market_and_commit", fail_commit)

    with pytest.raises(TimeoutError):
        await smallcap_rotation.execute(session, researcher)

    assert "r_marker" not in smallcap_rotation._last_adjustment_date
