"""
Celery 应用配置

包含：
  - Celery 实例创建与 broker/backend 配置
  - 任务模块注册
  - Beat 定时调度计划
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "cyber_invest",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.tasks.maintenance",       # 运维任务（ping 等）
        "app.tasks.trading_tasks",      # 交易相关任务
        "app.tasks.researcher_tasks",   # 研究员相关任务
        "app.tasks.news_tasks",         # 资讯相关任务
    ],
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
)

# ── Beat 定时调度计划 ──
# 注意：仅在启动 celery beat 时生效
# 启动命令：celery -A app.core.celery_app beat --loglevel=info
celery_app.conf.beat_schedule = {
    # 每个交易日 09:15 重置账户每日盈亏
    "trading-reset-daily-pnl": {
        "task": "trading.reset_daily_pnl",
        "schedule": crontab(hour=9, minute=15, day_of_week="1-5"),
    },
    # 交易时段每 30 秒刷新持仓现价（生产环境启用）
    # "trading-update-positions-price": {
    #     "task": "trading.update_positions_price",
    #     "schedule": 30.0,
    # },
    # 每个交易日 15:30 生成交易日报
    "trading-generate-daily-report": {
        "task": "trading.generate_daily_report",
        "schedule": crontab(hour=15, minute=30, day_of_week="1-5"),
    },
    # 每个交易日 16:00 刷新研究员统计数据
    "researcher-refresh-stats": {
        "task": "researcher.refresh_stats",
        "schedule": crontab(hour=16, minute=0, day_of_week="1-5"),
    },
    # 每 5 分钟抓取最新资讯（交易日 08:00-18:00）
    "news-fetch-latest": {
        "task": "news.fetch_latest",
        "schedule": crontab(minute="*/5", hour="8-18", day_of_week="1-5"),
    },
    # 每 15 分钟更新热门排名
    "news-update-hot-rankings": {
        "task": "news.update_hot_rankings",
        "schedule": crontab(minute="*/15", hour="8-18", day_of_week="1-5"),
    },
}
