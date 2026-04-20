"""Deprecated — use ``app.core.container.get_container().redis`` instead.

This module previously created a module-level Redis client that bypassed the
container lifecycle.  All new code should rely on ``RedisFactory`` via
``AppContainer``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.core.container import get_container

if TYPE_CHECKING:
    from redis.asyncio import Redis


async def get_redis() -> AsyncIterator[Redis]:
    """Backward-compatible dependency, delegates to container."""
    async for client in get_container().redis_dependency():
        yield client
