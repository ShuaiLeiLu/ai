from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from app.integrations.akshare.client import StockQuote
from app.modules.trading.schemas import DEFAULT_INITIAL_CAPITAL
from app.modules.trading.service import TradingService


def test_empty_account_snapshot_uses_consistent_initial_capital() -> None:
    service = TradingService()

    account = service.empty_account()

    assert account.initial_capital == DEFAULT_INITIAL_CAPITAL
    assert account.total_asset == DEFAULT_INITIAL_CAPITAL
    assert account.available_cash == DEFAULT_INITIAL_CAPITAL
    assert account.holding_value == 0
    assert account.daily_pnl == 0


def test_replay_records_calculates_realized_pnl_from_true_cost_basis() -> None:
    service = TradingService()
    buy_time = datetime(2026, 4, 20, 9, 30, 0)
    sell_time = datetime(2026, 4, 21, 10, 0, 0)

    records = [
        SimpleNamespace(
            id="trd_buy",
            symbol="000001",
            name="平安银行",
            side="buy",
            quantity=100,
            price=10.0,
            commission=5.0,
            created_at=buy_time,
        ),
        SimpleNamespace(
            id="trd_sell",
            symbol="000001",
            name="平安银行",
            side="sell",
            quantity=100,
            price=12.0,
            commission=6.2,
            created_at=sell_time,
        ),
    ]

    replay = service._replay_records(records, initial_capital=DEFAULT_INITIAL_CAPITAL)
    buy_record = replay.record_map["trd_buy"]
    sell_record = replay.record_map["trd_sell"]

    assert buy_record.cost_price == 10.05
    assert sell_record.cost_price == 10.05
    assert sell_record.realized_pnl == 188.8
    assert sell_record.realized_pnl_pct == 0.1879
    assert sell_record.hold_days == 1.0
    assert replay.daily_equity["2026-04-20"] == 999995.0
    assert replay.daily_equity["2026-04-21"] == 1000188.8


def test_apply_quotes_to_positions_marks_account_to_market() -> None:
    service = TradingService()
    positions = [
        SimpleNamespace(
            symbol="000001",
            name="平安银行",
            quantity=200,
            cost_price=10.0,
            current_price=10.0,
            pnl=0.0,
        ),
    ]
    quote_map = {
        "000001": StockQuote(
            symbol="000001",
            name="平安银行",
            price=10.8,
            change=0.5,
            change_pct=4.85,
            open=10.3,
            high=10.9,
            low=10.2,
            prev_close=10.3,
            volume=1000,
            amount=10800,
            timestamp="2026-04-22 10:00:00",
        )
    }

    holding_value, floating_daily_pnl = service._apply_quotes_to_positions(positions, quote_map)

    assert positions[0].current_price == 10.8
    assert positions[0].pnl == 160.0
    assert holding_value == 2160.0
    assert floating_daily_pnl == 100.0


def test_infer_initial_capital_is_fixed_to_one_million() -> None:
    service = TradingService()

    any_account = SimpleNamespace(
        total_asset=100_380.0,
        available_cash=9_700.0,
        holding_value=90_680.0,
    )

    assert service._infer_initial_capital(any_account) == DEFAULT_INITIAL_CAPITAL
    assert DEFAULT_INITIAL_CAPITAL == 1_000_000.0
