from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from redis.asyncio import Redis


class RedisFactory:
    """Builds and manages Redis async client."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: Redis | None = None

    def get_client(self) -> Redis:
        if self._client is None:
            from redis.asyncio import Redis

            self._client = Redis.from_url(self._settings.redis_url, decode_responses=True)
        return self._client

    async def redis_dependency(self) -> AsyncIterator[Redis]:
        yield self.get_client()

    async def shutdown(self) -> None:
        if self._client is None:
            return
        await self._client.aclose()
        self._client = None
