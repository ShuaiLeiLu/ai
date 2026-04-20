"""
交易相关定时任务

任务列表：
  - reset_daily_pnl: 每日开盘前重置所有账户的 daily_pnl
  - update_positions_price: 模拟更新持仓现价和盈亏（生产环境接入行情源）
  - generate_daily_report: 每日收盘后生成交易日报
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.celery_app import celery_app
from app.tasks.base import LoggedTask

logger = logging.getLogger(__name__)


@celery_app.task(base=LoggedTask, name="trading.reset_daily_pnl")
def reset_daily_pnl() -> dict:
    """每日开盘前重置所有模拟账户的 daily_pnl 为 0

    调度时机：每个交易日 09:15 执行
    当前为骨架实现，数据库就绪后替换为真实 SQL 批量更新。
    """
    logger.info("[trading.reset_daily_pnl] 开始重置每日盈亏...")
    # TODO: 数据库就绪后执行：
    # UPDATE trading_accounts SET daily_pnl = 0, updated_at = now()
    reset_count = 0  # 占位
    logger.info("[trading.reset_daily_pnl] 完成，重置 %d 个账户", reset_count)
    return {"status": "ok", "reset_count": reset_count, "executed_at": datetime.now(tz=UTC).isoformat()}


@celery_app.task(base=LoggedTask, name="trading.update_positions_price")
def update_positions_price() -> dict:
    """定期刷新持仓现价和浮动盈亏

    调度时机：交易时段每 30 秒执行一次
    当前为骨架实现，生产环境对接行情数据源。
    """
    logger.info("[trading.update_positions_price] 开始刷新持仓现价...")
    # TODO: 生产环境实现步骤：
    # 1. 查询所有持仓的 symbol 列表
    # 2. 批量获取最新行情价格
    # 3. 更新 positions.current_price 和 unrealized_pnl
    # 4. 更新 trading_accounts.holding_value 和 total_asset
    updated_count = 0  # 占位
    logger.info("[trading.update_positions_price] 完成，刷新 %d 条持仓", updated_count)
    return {"status": "ok", "updated_count": updated_count, "executed_at": datetime.now(tz=UTC).isoformat()}


@celery_app.task(base=LoggedTask, name="trading.generate_daily_report")
def generate_daily_report() -> dict:
    """收盘后生成交易日报

    调度时机：每个交易日 15:30 执行
    内容：今日盈亏、持仓变化、成交记录汇总。
    """
    logger.info("[trading.generate_daily_report] 开始生成交易日报...")
    # TODO: 数据库就绪后实现：
    # 1. 聚合当日 trade_records
    # 2. 计算当日盈亏
    # 3. 生成报告存入 documents 表或发送通知
    logger.info("[trading.generate_daily_report] 完成")
    return {"status": "ok", "executed_at": datetime.now(tz=UTC).isoformat()}
