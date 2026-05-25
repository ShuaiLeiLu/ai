"""策略调度引擎。

职责边界：
  - 本文件只负责任务编排和策略分发；
  - 每个策略独立放在 app.engine.strategies 下；
  - 模拟盘撮合、T+1、交易日志、风控检查放在 app.engine.paper_trading 下。

这个结构更接近 RQAlpha 的接入方式：调度器提供运行上下文，
策略脚本只暴露 execute / execute_intraday 入口。
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.paper_trading.risk import check_limit_up_open
from app.engine.strategies.registry import get_strategy, strategy_type_for
from app.models.researcher import Researcher

logger = logging.getLogger(__name__)


async def execute_daily_rotation(session: AsyncSession) -> dict:
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

    total_trades = 0
    details = []
    for researcher in researchers:
        strategy_type = strategy_type_for(researcher)
        strategy = get_strategy(strategy_type)
        try:
            trades = await strategy.execute(session, researcher)
            total_trades += trades
            details.append({
                "researcher": researcher.name,
                "strategy_type": strategy.strategy_type,
                "trades": trades,
            })
            logger.info(
                "[策略引擎] %s/%s 执行完成，成交 %d 笔",
                researcher.name,
                strategy.strategy_type,
                trades,
            )
        except Exception as exc:
            logger.error("[策略引擎] %s 执行失败: %s", researcher.name, exc)
            details.append({
                "researcher": researcher.name,
                "strategy_type": strategy.strategy_type,
                "error": str(exc),
            })

    return {
        "status": "ok",
        "total_trades": total_trades,
        "details": details,
        "executed_at": datetime.now(tz=UTC).isoformat(),
    }


async def execute_intraday_confirmation(session: AsyncSession) -> dict:
    """Execute strategies that expose an intraday confirmation hook."""
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
        if strategy.execute_intraday is None:
            continue
        try:
            trades = await strategy.execute_intraday(session, researcher)
            total_trades += trades
            details.append({
                "researcher": researcher.name,
                "strategy_type": strategy.strategy_type,
                "trades": trades,
            })
        except Exception as exc:
            logger.error("[策略引擎] %s 盘中确认失败: %s", researcher.name, exc)
            details.append({
                "researcher": researcher.name,
                "strategy_type": strategy.strategy_type,
                "error": str(exc),
            })

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
