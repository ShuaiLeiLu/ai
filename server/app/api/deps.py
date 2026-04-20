"""
FastAPI 依赖注入

提供：
  - db_session_dependency: 必须成功获取 AsyncSession（适用于数据库就绪的接口）
  - get_optional_session: 尝试获取 AsyncSession，失败时返回 None（支持降级）
  - redis_dependency: Redis 客户端
  - settings_dependency: 全局配置
"""
from __future__ import annotations

import logging
import time as _time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.container import AppContainer, get_container

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


def container_dependency() -> AppContainer:
    return get_container()


async def db_session_dependency(
    container: AppContainer = Depends(container_dependency),
) -> AsyncIterator[AsyncSession]:
    """必须获取数据库 session（数据库不可用则报 500）"""
    async for session in container.session_dependency():
        yield session


# ── schema 检测缓存 ──
# 首次请求检测 DB 连通性和表结构，成功后缓存结果，避免每次请求重复检测
# 失败时每 30 秒重试一次，防止 DB 恢复后无法自动切换
_db_ready: bool | None = None          # None=未检测, True=可用, False=不可用
_db_ready_checked_at: float = 0.0      # 上次检测时间戳
_DB_RETRY_INTERVAL: float = 30.0       # 失败后重试间隔（秒）


async def _check_db_ready() -> bool:
    """检测数据库连通性和 schema 就绪状态（带缓存）"""
    global _db_ready, _db_ready_checked_at
    now = _time.monotonic()

    # 已确认可用 → 直接返回
    if _db_ready is True:
        return True
    # 已确认不可用且未到重试时间 → 直接返回
    if _db_ready is False and (now - _db_ready_checked_at) < _DB_RETRY_INTERVAL:
        return False

    # 执行检测
    from sqlalchemy import text
    _db_ready_checked_at = now
    try:
        container = get_container()
        session_factory = container.database.session_factory
        session = session_factory()
        try:
            await session.execute(text("SELECT id, phone FROM users LIMIT 0"))
            await session.rollback()
            _db_ready = True
            logger.info("数据库连通性检测通过，启用 DB 模式")
            return True
        finally:
            await session.close()
    except Exception:
        _db_ready = False
        logger.debug("数据库不可用或 schema 未迁移，降级到内存 mock 模式（%.0f 秒后重试）", _DB_RETRY_INTERVAL)
        return False


async def get_optional_session() -> AsyncIterator[AsyncSession | None]:
    """尝试获取数据库 session，连接失败时 yield None（支持降级到 mock）。

    优化：首次请求检测 DB，通过后缓存结果，后续请求直接创建 session 无额外开销。
    """
    if not await _check_db_ready():
        yield None
        return

    container = get_container()
    session = container.database.session_factory()
    try:
        yield session
    finally:
        await session.close()


async def redis_dependency(
    container: AppContainer = Depends(container_dependency),
) -> AsyncIterator[Redis]:
    async for client in container.redis_dependency():
        yield client


def settings_dependency() -> Settings:
    return container_dependency().settings
