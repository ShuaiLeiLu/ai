from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from app.engine.paper_trading.executor import do_buy, do_sell
from app.integrations.openclaw.client import OpenClawTradePushClient
from app.integrations.openclaw.trade_push import (
    flush_strategy_trade_pushes,
    queue_strategy_trade_push,
)


def _researcher(**overrides: object) -> SimpleNamespace:
    data = {
        "id": "r_strategy",
        "name": "策略研究员",
        "prompt": "按策略执行模拟盘交易",
        "strategy_config": {"strategy_type": "smallcap_rotation"},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _account(**overrides: object) -> SimpleNamespace:
    data = {
        "id": "acct_strategy",
        "researcher_id": "r_strategy",
        "user_id": "u_owner",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _record(**overrides: object) -> SimpleNamespace:
    data = {
        "id": "trd_001",
        "account_id": "acct_strategy",
        "symbol": "600000",
        "name": "浦发银行",
        "side": "buy",
        "quantity": 100,
        "price": 10.25,
        "commission": 5.0,
        "created_at": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class FakeStrategySession:
    def __init__(self) -> None:
        self.info: dict[str, object] = {}
        self.added: list[object] = []
        self.deleted: list[object] = []

    def add(self, item: object) -> None:
        self.added.append(item)

    async def delete(self, item: object) -> None:
        self.deleted.append(item)

    async def flush(self) -> None:
        return None


@pytest.fixture
def strategy_executor_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_market_snapshot(*_args: object, **_kwargs: object) -> dict[str, object]:
        return {}

    async def fake_reflection(*_args: object, **_kwargs: object) -> str:
        return "策略成交复盘"

    async def fake_refresh(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(
        "app.engine.paper_trading.executor.build_trade_market_snapshot",
        fake_market_snapshot,
    )
    monkeypatch.setattr(
        "app.engine.paper_trading.executor._trading_reflection_skill.build_trade_reflection",
        fake_reflection,
    )
    monkeypatch.setattr(
        "app.modules.trading.service.TradingService._refresh_account_snapshot",
        fake_refresh,
    )


def test_queue_strategy_trade_push_requires_created_strategy_researcher() -> None:
    session = SimpleNamespace(info={})

    assert queue_strategy_trade_push(
        session,
        researcher=_researcher(strategy_config=None),
        account=_account(),
        record=_record(),
        amount=1025.0,
        reason="策略买入",
    ) is False

    assert queue_strategy_trade_push(
        session,
        researcher=_researcher(),
        account=_account(researcher_id="other_researcher"),
        record=_record(),
        amount=1025.0,
        reason="策略买入",
    ) is False

    assert session.info.get("openclaw_strategy_trade_pushes") is None


def test_queue_strategy_trade_push_stores_one_event_per_strategy_trade() -> None:
    session = SimpleNamespace(info={})

    queued = queue_strategy_trade_push(
        session,
        researcher=_researcher(),
        account=_account(),
        record=_record(),
        amount=1025.0,
        reason="策略买入",
    )

    assert queued is True
    events = session.info["openclaw_strategy_trade_pushes"]
    assert len(events) == 1
    assert events[0]["event_type"] == "researcher_paper_trade"
    assert events[0]["event_id"] == "trd_001"
    assert events[0]["researcher_id"] == "r_strategy"
    assert events[0]["strategy_type"] == "smallcap_rotation"
    assert events[0]["trade"]["symbol"] == "600000"
    assert events[0]["trade"]["side"] == "buy"
    assert events[0]["trade"]["amount"] == 1025.0


@pytest.mark.asyncio
async def test_do_buy_queues_strategy_trade_push(strategy_executor_stubs: None) -> None:
    session = FakeStrategySession()
    researcher = _researcher()
    account = _account(available_cash=100_000.0, holding_value=0.0, total_asset=100_000.0)

    trade_count, _pnl = await do_buy(
        session,  # type: ignore[arg-type]
        researcher,  # type: ignore[arg-type]
        account,  # type: ignore[arg-type]
        {
            "symbol": "600000",
            "name": "浦发银行",
            "price": 10.0,
            "prev_close": 9.8,
            "volume": 100_000,
            "reason": "策略买入",
        },
        20_000.0,
        0.0003,
        5.0,
    )

    assert trade_count == 1
    events = session.info["openclaw_strategy_trade_pushes"]
    assert len(events) == 1
    assert events[0]["trade"]["side"] == "buy"
    assert events[0]["trade"]["symbol"] == "600000"


@pytest.mark.asyncio
async def test_do_sell_queues_strategy_trade_push(
    monkeypatch: pytest.MonkeyPatch,
    strategy_executor_stubs: None,
) -> None:
    async def fake_today_buys(*_args: object, **_kwargs: object) -> dict[str, int]:
        return {}

    monkeypatch.setattr(
        "app.engine.paper_trading.executor.load_today_buy_quantities",
        fake_today_buys,
    )
    session = FakeStrategySession()
    researcher = _researcher()
    account = _account(available_cash=10_000.0, holding_value=10_000.0, total_asset=20_000.0)
    position = SimpleNamespace(
        symbol="600000",
        name="浦发银行",
        quantity=100,
        cost_price=9.0,
        current_price=10.0,
        pnl=100.0,
    )

    trade_count, _pnl = await do_sell(
        session,  # type: ignore[arg-type]
        researcher,  # type: ignore[arg-type]
        account,  # type: ignore[arg-type]
        position,  # type: ignore[arg-type]
        10.0,
        {"prev_close": 9.8, "volume": 100_000},
        0.0003,
        0.001,
        5.0,
        "策略卖出",
    )

    assert trade_count == 1
    events = session.info["openclaw_strategy_trade_pushes"]
    assert len(events) == 1
    assert events[0]["trade"]["side"] == "sell"
    assert events[0]["trade"]["symbol"] == "600000"


@pytest.mark.asyncio
async def test_flush_strategy_trade_pushes_posts_every_queued_event_with_signature() -> None:
    session = SimpleNamespace(info={})
    queue_strategy_trade_push(
        session,
        researcher=_researcher(),
        account=_account(),
        record=_record(id="trd_001", side="buy"),
        amount=1025.0,
        reason="策略买入",
    )
    queue_strategy_trade_push(
        session,
        researcher=_researcher(),
        account=_account(),
        record=_record(id="trd_002", side="sell"),
        amount=980.0,
        reason="策略卖出",
    )

    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = OpenClawTradePushClient(
            endpoint_url="https://openclaw.example/webhooks/trades",
            secret="push-secret",
            http_client=http_client,
        )
        delivered = await flush_strategy_trade_pushes(session, client=client)

    assert delivered == 2
    assert len(requests) == 2
    payloads = [json.loads(request.content.decode("utf-8")) for request in requests]
    assert [payload["event_id"] for payload in payloads] == ["trd_001", "trd_002"]
    assert all(request.headers.get("x-openclaw-signature") for request in requests)
    assert session.info["openclaw_strategy_trade_pushes"] == []
