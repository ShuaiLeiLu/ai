from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from app.engine import strategy_engine


class FakeScalarResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def all(self) -> list[object]:
        return self._values


class FakeResult:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def scalars(self) -> FakeScalarResult:
        return FakeScalarResult(self._values)


class FakeSession:
    def __init__(self, researchers: list[object]) -> None:
        self.researchers = researchers

    async def execute(self, stmt: object) -> FakeResult:
        return FakeResult(self.researchers)

    async def get(self, model: object, entity_id: str) -> object | None:
        return next(
            (researcher for researcher in self.researchers if researcher.id == entity_id),
            None,
        )


@pytest.mark.asyncio
async def test_daily_rotation_isolates_timeout_per_researcher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fast = SimpleNamespace(id="r_fast", name="快速研究员")
    slow = SimpleNamespace(id="r_slow", name="慢研究员")
    session = FakeSession([fast, slow])

    async def fast_execute(session: object, researcher: object) -> int:
        return 2

    async def slow_execute(session: object, researcher: object) -> int:
        await asyncio.sleep(0.05)
        return 99

    strategies = {
        "fast": SimpleNamespace(strategy_type="fast", execute=fast_execute),
        "slow": SimpleNamespace(strategy_type="slow", execute=slow_execute),
    }
    monkeypatch.setattr(
        strategy_engine,
        "strategy_type_for",
        lambda researcher: researcher.id.removeprefix("r_"),
    )
    monkeypatch.setattr(
        strategy_engine,
        "get_strategy",
        lambda strategy_type: strategies[strategy_type],
    )

    result = await strategy_engine.execute_daily_rotation(session, per_researcher_timeout=0.001)

    assert result["status"] == "ok"
    assert result["total_trades"] == 2
    assert result["details"] == [
        {"researcher": "快速研究员", "strategy_type": "fast", "trades": 2},
        {"researcher": "慢研究员", "strategy_type": "slow", "error": "timeout"},
    ]


@pytest.mark.asyncio
async def test_timeout_handler_uses_researcher_name_captured_before_rollback() -> None:
    class ExpiringResearcher:
        id = "r_slow"

        def __init__(self) -> None:
            self.expired = False

        @property
        def name(self) -> str:
            if self.expired:
                raise AssertionError("researcher.name was loaded after rollback")
            return "慢研究员"

    researcher = ExpiringResearcher()

    class RollbackSession:
        async def rollback(self) -> None:
            researcher.expired = True

    async def slow_execute(session: object, researcher: object) -> int:
        await asyncio.sleep(0.05)
        return 99

    trades, detail = await strategy_engine._run_strategy_for_researcher(
        session=RollbackSession(),
        researcher=researcher,  # type: ignore[arg-type]
        strategy_type="slow",
        strategy_name="slow",
        execute=slow_execute,
        timeout_seconds=0.001,
        action_label="执行",
    )

    assert trades == 0
    assert detail == {"researcher": "慢研究员", "strategy_type": "slow", "error": "timeout"}


@pytest.mark.asyncio
async def test_daily_rotation_does_not_reload_config_after_timeout_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ExpiringResearcher:
        def __init__(self, researcher_id: str, name: str, strategy_type: str) -> None:
            self.id = researcher_id
            self.name = name
            self.strategy_type = strategy_type
            self.expired = False

        @property
        def strategy_config(self) -> dict:
            if self.expired:
                raise AssertionError("strategy_config was loaded after rollback")
            return {"strategy_type": self.strategy_type}

    slow = ExpiringResearcher("r_slow", "慢研究员", "slow")
    fast = ExpiringResearcher("r_fast", "快速研究员", "fast")

    class ExpiringSession(FakeSession):
        async def rollback(self) -> None:
            for researcher in self.researchers:
                researcher.expired = True

        async def get(self, model: object, entity_id: str) -> object | None:
            researcher = next(
                item for item in self.researchers if item.id == entity_id
            )
            return SimpleNamespace(
                id=researcher.id,
                name=researcher.name,
                strategy_config={"strategy_type": researcher.strategy_type},
            )

    async def slow_execute(session: object, researcher: object) -> int:
        await asyncio.sleep(0.05)
        return 99

    async def fast_execute(session: object, researcher: object) -> int:
        return 1

    strategies = {
        "slow": SimpleNamespace(strategy_type="slow", execute=slow_execute),
        "fast": SimpleNamespace(strategy_type="fast", execute=fast_execute),
    }
    monkeypatch.setattr(
        strategy_engine,
        "strategy_type_for",
        lambda researcher: researcher.strategy_config["strategy_type"],
    )
    monkeypatch.setattr(
        strategy_engine,
        "get_strategy",
        lambda strategy_type: strategies[strategy_type],
    )

    result = await strategy_engine.execute_daily_rotation(
        ExpiringSession([slow, fast]),  # type: ignore[arg-type]
        per_researcher_timeout=0.001,
    )

    assert result["status"] == "ok"
    assert result["total_trades"] == 1
