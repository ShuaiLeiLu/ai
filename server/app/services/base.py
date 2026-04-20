from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
