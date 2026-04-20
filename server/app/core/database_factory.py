from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings


class DatabaseFactory:
    """Builds and manages async database primitives."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    def initialize(self) -> None:
        if self._engine is not None and self._session_factory is not None:
            return

        self._engine = create_async_engine(
            self._settings.database_url,
            pool_size=10,            # 连接池常驻连接数
            max_overflow=20,         # 超出 pool_size 时允许的额外连接数
            pool_recycle=300,        # 连接回收周期（秒），防止远程长连接被防火墙断开
            pool_pre_ping=False,     # 关闭 pre_ping，用 pool_recycle 保活，避免每次取连接额外往返
            pool_timeout=10,         # 从池中获取连接的超时时间（秒）
            echo=False,              # 生产环境关闭 SQL 日志
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )

    @property
    def engine(self) -> AsyncEngine:
        self.initialize()
        if self._engine is None:
            raise RuntimeError("Database engine is not initialized.")
        return self._engine

    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        self.initialize()
        if self._session_factory is None:
            raise RuntimeError("Database session factory is not initialized.")
        return self._session_factory

    async def session_dependency(self) -> AsyncIterator[AsyncSession]:
        async with self.session_factory() as session:
            yield session

    async def shutdown(self) -> None:
        if self._engine is None:
            return
        await self._engine.dispose()
        self._engine = None
        self._session_factory = None
