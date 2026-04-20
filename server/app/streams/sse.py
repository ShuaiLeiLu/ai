from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from sse_starlette import EventSourceResponse


async def heartbeat_stream() -> AsyncIterator[dict[str, str]]:
    while True:
        yield {
            "event": "heartbeat",
            "data": datetime.now(tz=UTC).isoformat(),
        }
        break


def create_sse_response(generator: AsyncIterator[dict[str, str]]) -> EventSourceResponse:
    return EventSourceResponse(generator)
