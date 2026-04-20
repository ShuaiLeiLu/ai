"""
资讯相关定时任务

任务列表：
  - fetch_latest_news: 抓取最新资讯
  - generate_ai_interpretation: 使用 LLM 生成资讯 AI 解读
  - update_hot_rankings: 更新热门资讯和热股排名
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from app.core.celery_app import celery_app
from app.tasks.base import LoggedTask

logger = logging.getLogger(__name__)


@celery_app.task(base=LoggedTask, name="news.fetch_latest")
def fetch_latest_news() -> dict:
    """抓取最新资讯

    调度时机：每 5 分钟执行一次（交易日 08:00-18:00）
    数据源：财联社、交易所公告、券商研报等

    流程（生产环境实现）：
      1. 调用各资讯源 API 获取增量数据
      2. 解析并存入 news 表
      3. 触发 AI 解读任务
    """
    logger.info("[news.fetch_latest] 开始抓取资讯...")
    # TODO: 接入 NewsProviderClient
    fetched_count = 0
    logger.info("[news.fetch_latest] 完成，新增 %d 条资讯", fetched_count)
    return {"status": "ok", "fetched_count": fetched_count, "executed_at": datetime.now(tz=UTC).isoformat()}


@celery_app.task(base=LoggedTask, name="news.generate_ai_interpretation")
def generate_ai_interpretation(news_id: str) -> dict:
    """使用 LLM 为单条资讯生成 AI 解读

    调度时机：由 fetch_latest_news 触发
    流程：
      1. 查询资讯内容
      2. 构建 prompt 调用 LLM
      3. 将解读结果存入 ai_interpretations 表
    """
    logger.info("[news.generate_ai_interpretation] 生成资讯 %s 的 AI 解读...", news_id)
    # TODO: 接入 LLMClient
    logger.info("[news.generate_ai_interpretation] 完成")
    return {"status": "ok", "news_id": news_id, "executed_at": datetime.now(tz=UTC).isoformat()}


@celery_app.task(base=LoggedTask, name="news.update_hot_rankings")
def update_hot_rankings() -> dict:
    """更新热门资讯和热股排名

    调度时机：每 15 分钟执行一次
    逻辑：基于浏览量、评论数、相关股票涨幅等综合计算热度分
    """
    logger.info("[news.update_hot_rankings] 开始更新热门排名...")
    # TODO: 数据库就绪后实现
    logger.info("[news.update_hot_rankings] 完成")
    return {"status": "ok", "executed_at": datetime.now(tz=UTC).isoformat()}
