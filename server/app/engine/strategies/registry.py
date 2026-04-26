from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.researcher import Researcher

from . import sentiment_ultrashort, smallcap_rotation

StrategyExecute = Callable[[AsyncSession, Researcher], Awaitable[int]]


@dataclass(frozen=True)
class StrategySpec:
    strategy_type: str
    execute: StrategyExecute
    execute_intraday: StrategyExecute | None = None


DEFAULT_STRATEGY_TYPE = smallcap_rotation.STRATEGY_TYPE

_STRATEGIES: dict[str, StrategySpec] = {
    smallcap_rotation.STRATEGY_TYPE: StrategySpec(
        strategy_type=smallcap_rotation.STRATEGY_TYPE,
        execute=smallcap_rotation.execute,
    ),
    sentiment_ultrashort.STRATEGY_TYPE: StrategySpec(
        strategy_type=sentiment_ultrashort.STRATEGY_TYPE,
        execute=sentiment_ultrashort.execute,
        execute_intraday=sentiment_ultrashort.execute_intraday,
    ),
}


def strategy_type_for(researcher: Researcher) -> str:
    config = researcher.strategy_config or {}
    return str(config.get("strategy_type") or DEFAULT_STRATEGY_TYPE)


def get_strategy(strategy_type: str) -> StrategySpec:
    return _STRATEGIES.get(strategy_type, _STRATEGIES[DEFAULT_STRATEGY_TYPE])


def list_strategy_types() -> list[str]:
    return sorted(_STRATEGIES)
