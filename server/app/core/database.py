"""Deprecated — use ``app.core.container.get_container().database`` instead.

This module previously created module-level engine / session-factory singletons
which bypassed the container lifecycle (startup / shutdown).  All new code
should rely on ``DatabaseFactory`` via ``AppContainer``.
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.container import get_container


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Backward-compatible dependency, delegates to container."""
    async for session in get_container().session_dependency():
        yield session
