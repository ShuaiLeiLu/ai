"""
研究员相关定时任务

任务列表：
  - researcher_self_drive: 执行研究员的自驱动任务列表
  - refresh_researcher_stats: 刷新研究员统计数据（胜率、收益等）
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.celery_app import celery_app
from app.tasks.base import LoggedTask

logger = logging.getLogger(__name__)


@celery_app.task(base=LoggedTask, name="researcher.self_drive")
def researcher_self_drive(researcher_id: str) -> dict:
    """执行研究员的自驱动任务

    调度时机：根据研究员配置的 self_drive_tasks 定时触发
    示例任务：盘前检查行业强弱、盘中监控龙头分歧转一致 等

    流程（数据库就绪后实现）：
      1. 查询研究员的 self_drive_tasks 配置
      2. 根据任务类型调用 LLM 生成分析内容
      3. 将结果存入 documents 表或推送通知
    """
    logger.info("[researcher.self_drive] 开始执行研究员 %s 的自驱动任务...", researcher_id)
    # TODO: 接入 LLM 和数据库
    logger.info("[researcher.self_drive] 完成")
    return {"status": "ok", "researcher_id": researcher_id, "executed_at": datetime.now(tz=UTC).isoformat()}


@celery_app.task(base=LoggedTask, name="researcher.refresh_stats")
def refresh_researcher_stats() -> dict:
    """刷新所有研究员的统计数据

    调度时机：每日收盘后 16:00 执行
    计算内容：30 日胜率、今日盈亏、累计收益率
    """
    logger.info("[researcher.refresh_stats] 开始刷新研究员统计...")
    # TODO: 数据库就绪后实现：
    # 1. 查询每个研究员关联的 trading_account
    # 2. 计算 30d 胜率和收益数据
    # 3. 更新 researchers 表的 win_rate_30d, today_pnl 等字段
    updated_count = 0
    logger.info("[researcher.refresh_stats] 完成，刷新 %d 位研究员", updated_count)
    return {"status": "ok", "updated_count": updated_count, "executed_at": datetime.now(tz=UTC).isoformat()}
