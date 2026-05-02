from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.integrations.akshare.client import LimitUpStock
from app.modules.trading.reflection_skill import TradingReflectionSkill
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


def test_ai_reflection_log_extracts_render_sections() -> None:
    content = (
        "## 交易复盘\n"
        "- 买入九芝堂，仓位 10%。\n\n"
        "## 执行反思\n"
        "- 成交价格符合预期。\n\n"
        "## 次日展望\n"
        "- 观察开盘承接。"
    )

    sections = TradingService._extract_analysis_sections("analysis", content)

    assert [section.title for section in sections] == ["交易复盘", "执行反思", "次日展望"]
    assert "买入九芝堂" in sections[0].content
    assert "开盘承接" in sections[2].content


def test_ai_reflection_log_keeps_workflow_subsections() -> None:
    content = (
        "## 交易复盘\n"
        "### 操作播报\n"
        "刚买入九芝堂。\n\n"
        "### 盘面数据\n"
        "本次日志未提供盘口快照。\n\n"
        "## 执行反思\n"
        "### 纪律检查\n"
        "仓位符合规则。\n\n"
        "## 次日展望\n"
        "### 观察重点\n"
        "观察开盘承接。"
    )

    sections = TradingService._extract_analysis_sections("analysis", content)

    assert [section.title for section in sections] == ["交易复盘", "执行反思", "次日展望"]
    assert "操作播报" in sections[0].content
    assert "盘面数据" in sections[0].content
    assert "纪律检查" in sections[1].content


def test_fallback_trade_reflection_uses_workflow_shape_for_sell() -> None:
    content = TradingReflectionSkill().build_fallback_reflection(
        researcher_name="阿发",
        researcher_prompt="超短轮动，严格止损",
        trade_context={
            "side": "sell",
            "symbol": "600482",
            "name": "中国动力",
            "price": 39.62,
            "quantity": 5600,
            "amount": 221872,
            "commission": 5,
            "cost_price": 39.10,
            "realized_pnl": 2912,
            "realized_pnl_pct": 0.0133,
            "position_ratio": 0.22,
            "total_asset": 1126700,
            "available_cash": 636000,
            "reason": "盘中冲高后按纪律止盈",
            "market_snapshot": {
                "snapshot_at": "2026-04-14 10:00:49",
                "quote": {
                    "price": 39.62,
                    "change_pct": 1.33,
                    "open": 39.1,
                    "high": 39.8,
                    "low": 38.9,
                    "amount": 302000000,
                    "turnover_ratio": 3.2,
                    "volume_ratio": 1.6,
                    "main_net_inflow": 598400,
                    "main_net_inflow_pct": 0.8,
                    "industry": "船舶制造",
                },
                "industry": {
                    "name": "船舶制造",
                    "change_pct": 2.2,
                    "total_amount": 128.6,
                    "net_inflow": 4.1,
                    "rise_count": 8,
                    "fall_count": 2,
                    "leading_stock": "中国动力",
                    "leading_stock_pct": 1.33,
                },
                "market_sentiment": {
                    "limit_up_count": 42,
                    "limit_down_count": 8,
                    "multi_board_count": 9,
                    "highest_consecutive": 4,
                    "top_limit_industries": [{"industry": "军工", "limit_up_count": 5}],
                },
            },
        },
    )

    assert "## 交易复盘" in content
    assert "## 执行反思" in content
    assert "## 次日展望" in content
    assert "| 股票名称 | 股票代码 | 买入价格 | 卖出价格 |" in content
    assert "| 中国动力 | 600482 | 39.10 元 | 39.62 元 |" in content
    assert "交易结果" in content
    assert "本次日志未提供/待接入" not in content
    assert "主力净流入" in content
    assert "+0.01 亿" in content
    assert "涨停家数" in content
    assert "船舶制造" in content


@pytest.mark.asyncio
async def test_build_trade_market_snapshot_collects_real_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TradingService()
    quote = SimpleNamespace(
        symbol="600482",
        name="中国动力",
        price=39.62,
        change=0.52,
        change_pct=1.33,
        open=39.1,
        high=39.8,
        low=38.9,
        prev_close=39.1,
        volume=10000,
        amount=302000000,
        turnover_ratio=3.2,
        volume_ratio=1.6,
        industry="船舶制造",
        main_net_inflow=598400,
        main_net_inflow_pct=0.8,
        timestamp="2026-04-14 10:00:49",
    )

    async def fake_run_sync(fn: object, *_args: object, **_kwargs: object) -> object:
        name = getattr(fn, "__name__", "")
        if name == "get_industry_boards":
            return [
                SimpleNamespace(
                    name="船舶制造",
                    change_pct=2.2,
                    total_volume=100,
                    total_amount=128.6,
                    net_inflow=4.1,
                    rise_count=8,
                    fall_count=2,
                    leading_stock="中国动力",
                    leading_stock_pct=1.33,
                )
            ]
        if name == "get_limit_up_pool":
            return [
                LimitUpStock(
                    symbol="600482",
                    name="中国动力",
                    change_pct=10,
                    price=42,
                    amount=500000000,
                    turnover_ratio=5,
                    seal_amount=100000000,
                    first_seal_time="093001",
                    last_seal_time="093001",
                    break_count=0,
                    consecutive=2,
                    industry="军工",
                )
            ]
        if name == "get_limit_down_pool":
            return []
        return []

    monkeypatch.setattr("app.modules.trading.service.run_sync", fake_run_sync)

    snapshot = await service._build_trade_market_snapshot("600482", quote)  # type: ignore[arg-type]

    assert snapshot["quote"]["main_net_inflow"] == 598400
    assert snapshot["industry"]["change_pct"] == 2.2
    assert snapshot["limit_up"]["consecutive"] == 2
    assert snapshot["market_sentiment"]["limit_up_count"] == 1


@pytest.mark.asyncio
async def test_async_get_stats_does_not_inject_calendar_today(monkeypatch: pytest.MonkeyPatch) -> None:
    service = TradingService()
    account = SimpleNamespace(id="acct_stats_no_today_test", total_asset=1005000.0)

    class FakeSession:
        async def execute(self, _stmt: object) -> _ScalarResult:
            return _ScalarResult(account)

    async def fake_load_replay(*_args: object, **_kwargs: object) -> tuple[list[object], object]:
        replay = SimpleNamespace(
            daily_equity={"2026-04-30": 1000000.0},
            sell_pnls=[],
            hold_days=[],
            record_map={},
        )
        return [SimpleNamespace()], replay

    async def fake_get_or_build_snapshots(*_args: object, **_kwargs: object) -> list[object]:
        return []

    monkeypatch.setattr(service, "_load_replay", fake_load_replay)
    monkeypatch.setattr(service, "_get_or_build_account_snapshots", fake_get_or_build_snapshots)

    stats = await service.async_get_stats(FakeSession(), "acct_stats_no_today_test")

    assert stats.equity_curve == []
    assert stats.daily_returns == []


@pytest.mark.asyncio
async def test_async_get_stats_prefers_persisted_account_snapshots(monkeypatch: pytest.MonkeyPatch) -> None:
    service = TradingService()
    account = SimpleNamespace(id="acct_stats_snapshot_history_test", total_asset=1005000.0)

    class FakeSession:
        async def execute(self, _stmt: object) -> _ScalarResult:
            return _ScalarResult(account)

        async def flush(self) -> None:
            pass

    async def fake_load_replay(*_args: object, **_kwargs: object) -> tuple[list[object], object]:
        replay = SimpleNamespace(
            daily_equity={"2026-03-19": 999000.0},
            sell_pnls=[],
            hold_days=[],
            record_map={},
        )
        return [SimpleNamespace(created_at=datetime(2026, 3, 19))], replay

    async def fake_get_or_build_snapshots(*_args: object, **_kwargs: object) -> list[object]:
        return [
            SimpleNamespace(trade_date=date(2026, 3, 19), total_asset=999700.0),
            SimpleNamespace(trade_date=date(2026, 3, 20), total_asset=1001200.0),
        ]

    monkeypatch.setattr(service, "_load_replay", fake_load_replay)
    monkeypatch.setattr(service, "_get_or_build_account_snapshots", fake_get_or_build_snapshots)

    stats = await service.async_get_stats(FakeSession(), "acct_stats_snapshot_history_test")

    assert [point.date for point in stats.equity_curve] == ["2026-03-19", "2026-03-20"]
    assert [item.date for item in stats.daily_returns] == ["2026-03-19", "2026-03-20"]
    assert stats.equity_curve[1].equity == 1001200.0


@pytest.mark.asyncio
async def test_generate_reflection_returns_clear_error_when_llm_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TradingService()
    account = SimpleNamespace(id="acct_reflect_error", total_asset=1000000.0, available_cash=900000.0)
    record_row = SimpleNamespace(id="tr_1")
    replay_record = SimpleNamespace(
        side="buy",
        symbol="000001",
        name="平安银行",
        price=10.0,
        quantity=1000,
        amount=10000.0,
        commission=5.0,
        cost_price=10.005,
        realized_pnl=None,
        realized_pnl_pct=None,
        position_ratio=0.01,
    )
    replay = SimpleNamespace(record_map={"tr_1": replay_record})

    async def fake_load_replay(*_args: object, **_kwargs: object) -> tuple[list[object], object]:
        return [record_row], replay

    async def fail_reflection(*_args: object, **_kwargs: object) -> str:
        raise RuntimeError("LLM 服务未配置")

    monkeypatch.setattr(service, "_load_replay", fake_load_replay)
    monkeypatch.setattr(
        "app.modules.trading.service._reflection_skill.build_trade_reflection",
        fail_reflection,
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.async_generate_reflection_for_latest_trade(
            SimpleNamespace(),
            account=account,
            researcher=None,
        )

    assert exc_info.value.status_code == 503
    assert "LLM 服务未配置" in str(exc_info.value.detail)
