"""策略调度引擎。

职责边界：
  - 本文件只负责任务编排和策略分发；
  - 每个策略独立放在 app.engine.strategies 下；
  - 模拟盘撮合、T+1、交易日志、风控检查放在 app.engine.paper_trading 下。

这个结构更接近 RQAlpha 的接入方式：调度器提供运行上下文，
策略脚本只暴露 execute / execute_intraday 入口。
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.paper_trading.risk import check_limit_up_open
from app.engine.strategies.registry import get_strategy, strategy_type_for
from app.models.researcher import Researcher

logger = logging.getLogger(__name__)

DEFAULT_RESEARCHER_STRATEGY_TIMEOUT_SECONDS = 90


async def _rollback_after_failure(session: AsyncSession, researcher_name: str) -> None:
    try:
        await session.rollback()
    except Exception:
        logger.exception("[策略引擎] %s 失败后回滚 session 异常", researcher_name)


async def _run_strategy_for_researcher(
    *,
    session: AsyncSession,
    researcher: Researcher,
    researcher_name: str | None = None,
    strategy_type: str,
    strategy_name: str,
    execute: Callable[[AsyncSession, Researcher], Awaitable[int]],
    timeout_seconds: float,
    action_label: str,
) -> tuple[int, dict]:
    researcher_name = researcher_name or researcher.name
    try:
        trades = await asyncio.wait_for(
            execute(session, researcher),
            timeout=timeout_seconds,
        )
        logger.info(
            "[策略引擎] %s/%s %s完成，成交 %d 笔",
            researcher_name,
            strategy_name,
            action_label,
            trades,
        )
        return trades, {
            "researcher": researcher_name,
            "strategy_type": strategy_name,
            "trades": trades,
        }
    except TimeoutError:
        await _rollback_after_failure(session, researcher_name)
        logger.exception(
            "[策略引擎] %s/%s %s超时，已跳过该研究员",
            researcher_name,
            strategy_name,
            action_label,
        )
        return 0, {
            "researcher": researcher_name,
            "strategy_type": strategy_name,
            "error": "timeout",
        }
    except Exception as exc:
        await _rollback_after_failure(session, researcher_name)
        logger.error(
            "[策略引擎] %s/%s %s失败: %s",
            researcher_name,
            strategy_type,
            action_label,
            exc,
        )
        return 0, {
            "researcher": researcher_name,
            "strategy_type": strategy_name,
            "error": str(exc),
        }


async def execute_daily_rotation(
    session: AsyncSession,
    per_researcher_timeout: float = DEFAULT_RESEARCHER_STRATEGY_TIMEOUT_SECONDS,
) -> dict:
    """Execute all active researchers that have a strategy_config."""
    stmt = select(Researcher).where(
        Researcher.status == "active",
        Researcher.strategy_config.isnot(None),
    )
    result = await session.execute(stmt)
    researchers = list(result.scalars().all())

    if not researchers:
        logger.info("[策略引擎] 没有需要执行策略的研究员")
        return {"status": "skip", "reason": "no_active_researchers"}

    candidates = [
        {
            "id": researcher.id,
            "name": researcher.name,
            "strategy_type": strategy_type_for(researcher),
        }
        for researcher in researchers
    ]

    total_trades = 0
    details = []
    for candidate in candidates:
        researcher = await session.get(Researcher, candidate["id"]) or next(
            item for item in researchers if item.id == candidate["id"]
        )
        strategy_type = candidate["strategy_type"]
        strategy = get_strategy(strategy_type)
        trades, detail = await _run_strategy_for_researcher(
            session=session,
            researcher=researcher,
            researcher_name=candidate["name"],
            strategy_type=strategy_type,
            strategy_name=strategy.strategy_type,
            execute=strategy.execute,
            timeout_seconds=per_researcher_timeout,
            action_label="执行",
        )
        total_trades += trades
        details.append(detail)

    return {
        "status": "ok",
        "total_trades": total_trades,
        "details": details,
        "executed_at": datetime.now(tz=UTC).isoformat(),
    }


async def execute_intraday_confirmation(
    session: AsyncSession,
    per_researcher_timeout: float = DEFAULT_RESEARCHER_STRATEGY_TIMEOUT_SECONDS,
) -> dict:
    """Execute strategies that expose an intraday confirmation hook."""
    stmt = select(Researcher).where(
        Researcher.status == "active",
        Researcher.strategy_config.isnot(None),
    )
    result = await session.execute(stmt)
    researchers = list(result.scalars().all())

    candidates = [
        {
            "id": researcher.id,
            "name": researcher.name,
            "strategy_type": strategy_type_for(researcher),
        }
        for researcher in researchers
    ]

    total_trades = 0
    details = []
    for candidate in candidates:
        researcher = await session.get(Researcher, candidate["id"]) or next(
            item for item in researchers if item.id == candidate["id"]
        )
        strategy_type = candidate["strategy_type"]
        strategy = get_strategy(strategy_type)
        if strategy.execute_intraday is None:
            continue
        trades, detail = await _run_strategy_for_researcher(
            session=session,
            researcher=researcher,
            researcher_name=candidate["name"],
            strategy_type=strategy_type,
            strategy_name=strategy.strategy_type,
            execute=strategy.execute_intraday,
            timeout_seconds=per_researcher_timeout,
            action_label="盘中确认",
        )
        total_trades += trades
        details.append(detail)

    if not details:
        logger.info("[策略引擎] 没有需要盘中确认的研究员")
        return {"status": "skip", "reason": "no_intraday_researchers"}

    return {
        "status": "ok",
        "total_trades": total_trades,
        "details": details,
        "executed_at": datetime.now(tz=UTC).isoformat(),
    }


async def check_limit_up(session: AsyncSession) -> dict:
    """14:00 generic paper-trading check for tracked limit-up holdings."""
    return await check_limit_up_open(session)


async def check_stop_loss(session: AsyncSession) -> dict:
    """Execute stop-loss checks for strategies that expose one."""
    from app.engine.strategies import smallcap_rotation

    stmt = select(Researcher).where(
        Researcher.status == "active",
        Researcher.strategy_config.isnot(None),
    )
    result = await session.execute(stmt)
    researchers = list(result.scalars().all())

    total_trades = 0
    details = []
    for researcher in researchers:
        strategy_type = strategy_type_for(researcher)
        strategy = get_strategy(strategy_type)
        execute_stop_loss = (
            smallcap_rotation.execute_stop_loss
            if strategy_type == smallcap_rotation.STRATEGY_TYPE
            else None
        )
        if execute_stop_loss is None:
            continue
        try:
            trades = await execute_stop_loss(session, researcher)
            total_trades += trades
            details.append({
                "researcher": researcher.name,
                "strategy_type": strategy.strategy_type,
                "trades": trades,
            })
        except Exception as exc:
            logger.error("[策略引擎] %s 止损检查失败: %s", researcher.name, exc)
            details.append({
                "researcher": researcher.name,
                "strategy_type": strategy.strategy_type,
                "error": str(exc),
            })

    if not details:
        return {"status": "skip", "reason": "no_stop_loss_researchers"}
    return {
        "status": "ok",
        "total_trades": total_trades,
        "details": details,
        "executed_at": datetime.now(tz=UTC).isoformat(),
    }
