from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.trading.service import TradingService


class _ScalarResult:
    def __init__(self, value: object | None) -> None:
        self._value = value

    def scalar_one_or_none(self) -> object | None:
        return self._value


@pytest.mark.asyncio
async def test_async_get_portfolio_uses_account_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    service = TradingService()
    account = SimpleNamespace(
        id="acct_snapshot_test",
        total_asset=998000.0,
        available_cash=120000.0,
        holding_value=878000.0,
        daily_pnl=3200.0,
    )

    async def fake_resolve_account_model(*_args: object, **_kwargs: object) -> object:
        return account

    async def fake_list_positions(*_args: object, **_kwargs: object) -> list[object]:
        return []

    async def fake_load_replay(*_args: object, **_kwargs: object) -> tuple[list[object], object]:
        replay = SimpleNamespace(
            daily_equity={"2000-01-01": 999500.0},
            sell_pnls=[],
            hold_days=[],
            record_map={},
        )
        return [], replay

    async def fail_refresh(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("detail read path must not trigger quote refresh")

    monkeypatch.setattr(service, "_resolve_account_model", fake_resolve_account_model)
    monkeypatch.setattr(service, "async_list_positions", fake_list_positions)
    monkeypatch.setattr(service, "_load_replay", fake_load_replay)
    monkeypatch.setattr(service, "_refresh_account_snapshot", fail_refresh)

    data = await service.async_get_portfolio(SimpleNamespace(), "u_demo", "r_demo")

    assert data.account.account_id == "acct_snapshot_test"
    assert data.account.total_asset == 998000.0
    assert data.account.available_cash == 120000.0
    assert data.account.holding_value == 878000.0
    assert data.account.daily_pnl == -1500.0
    assert data.account.total_pnl == -2000.0
    assert data.account.total_return == -0.002
    assert data.positions == []


@pytest.mark.asyncio
async def test_async_get_account_ignores_stale_raw_daily_pnl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TradingService()
    account = SimpleNamespace(
        id="acct_recent_pnl_test",
        total_asset=985031.32,
        available_cash=10000.0,
        holding_value=975031.32,
        daily_pnl=1750.0,
    )

    async def fake_resolve_account_model(*_args: object, **_kwargs: object) -> object:
        return account

    async def fake_load_replay(*_args: object, **_kwargs: object) -> tuple[list[object], object]:
        replay = SimpleNamespace(
            daily_equity={"2000-01-01": 998894.32},
            sell_pnls=[],
            hold_days=[],
            record_map={},
        )
        return [], replay

    monkeypatch.setattr(service, "_resolve_account_model", fake_resolve_account_model)
    monkeypatch.setattr(service, "_load_replay", fake_load_replay)

    data = await service.async_get_account(SimpleNamespace(), "u_recent", "r_recent")

    assert data.daily_pnl == -13863.0
    assert data.total_pnl == -14968.68
    assert data.total_return == -0.015


@pytest.mark.asyncio
async def test_async_list_positions_skips_sellable_quantity_query_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TradingService()

    class FakePositionRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def list_by_account(self, _account_id: str) -> list[object]:
            return [
                SimpleNamespace(
                    symbol="600654",
                    name="中安科",
                    quantity=1000,
                    cost_price=4.0,
                    current_price=4.2,
                    pnl=200.0,
                )
            ]

    async def fail_today_buy_quantities(*_args: object, **_kwargs: object) -> dict[str, int]:
        raise AssertionError("snapshot position reads must not query today's buys")

    monkeypatch.setattr("app.modules.trading.service.PositionRepository", FakePositionRepository)
    monkeypatch.setattr(service, "_load_today_buy_quantities", fail_today_buy_quantities)

    items = await service.async_list_positions(
        SimpleNamespace(),
        "acct_position_snapshot_test",
        cache_only=False,
    )

    assert len(items) == 1
    assert items[0].symbol == "600654"
    assert items[0].sellable_quantity is None
    assert items[0].pnl == 200.0


@pytest.mark.asyncio
async def test_async_list_positions_can_load_sellable_quantity_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TradingService()

    class FakePositionRepository:
        def __init__(self, _session: object) -> None:
            pass

        async def list_by_account(self, _account_id: str) -> list[object]:
            return [
                SimpleNamespace(
                    symbol="600654",
                    name="中安科",
                    quantity=1000,
                    cost_price=4.0,
                    current_price=4.2,
                    pnl=200.0,
                )
            ]

    async def fake_today_buy_quantities(*_args: object, **_kwargs: object) -> dict[str, int]:
        return {"600654": 300}

    monkeypatch.setattr("app.modules.trading.service.PositionRepository", FakePositionRepository)
    monkeypatch.setattr(service, "_load_today_buy_quantities", fake_today_buy_quantities)

    items = await service.async_list_positions(
        SimpleNamespace(),
        "acct_position_sellable_test",
        cache_only=False,
        include_sellable_quantity=True,
    )

    assert items[0].sellable_quantity == 700


@pytest.mark.asyncio
async def test_async_get_stats_uses_account_total_asset(monkeypatch: pytest.MonkeyPatch) -> None:
    service = TradingService()
    account = SimpleNamespace(id="acct_stats_snapshot_test", total_asset=1005000.0)

    class FakeSession:
        async def execute(self, _stmt: object) -> _ScalarResult:
            return _ScalarResult(account)

    async def fake_load_replay(*_args: object, **_kwargs: object) -> tuple[list[object], object]:
        replay = SimpleNamespace(
            daily_equity={},
            sell_pnls=[],
            hold_days=[],
            record_map={},
        )
        return [], replay

    monkeypatch.setattr(service, "_load_replay", fake_load_replay)

    stats = await service.async_get_stats(FakeSession(), "acct_stats_snapshot_test")

    assert stats.initial_capital == 1_000_000.0
    assert stats.total_asset == 1005000.0
    assert stats.risk.total_return == 0


def test_ai_reflection_log_shape_is_sectioned() -> None:
    content = TradingService._normalize_analysis_content(
        "analysis",
        "根据策略选股信号，买入九芝堂(000989)。",
    )

    assert "交易复盘" in content
    assert "执行反思" in content
    assert "次日展望" in content
    assert "买入九芝堂" in content


def test_ai_reflection_log_shape_keeps_structured_content() -> None:
    original = (
        "## 交易复盘\n"
        "- 买入原因\n\n"
        "## 执行反思\n"
        "- 成交正常\n\n"
        "## 次日展望\n"
        "- 观察开盘强弱"
    )
    content = TradingService._normalize_analysis_content("analysis", original)

    assert content == original
