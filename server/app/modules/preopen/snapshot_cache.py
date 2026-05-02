"""Redis snapshots for preopen dashboard data."""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, TypeVar
from uuid import uuid4

from pydantic import BaseModel, TypeAdapter

T = TypeVar("T")
logger = logging.getLogger(__name__)

SNAPSHOT_KEY_PREFIX = "preopen:snapshot:"
SNAPSHOT_LOCK_PREFIX = "preopen:snapshot-lock:"
SNAPSHOT_RETAIN_SECONDS = 3 * 24 * 60 * 60

_RELEASE_LOCK_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
  return redis.call("del", KEYS[1])
end
return 0
"""


@dataclass(frozen=True)
class SnapshotSpec[T]:
    name: str
    adapter: TypeAdapter[T]
    empty_factory: Callable[[], T]

    @property
    def redis_key(self) -> str:
        return f"{SNAPSHOT_KEY_PREFIX}{self.name}"

    @property
    def lock_key(self) -> str:
        return f"{SNAPSHOT_LOCK_PREFIX}{self.name}"


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def load_snapshot(redis: Any, spec: SnapshotSpec[T]) -> T | None:
    raw = await redis.get(spec.redis_key)
    if not raw:
        return None

    payload = json.loads(raw)
    return spec.adapter.validate_python(payload["data"])


async def load_snapshot_or_empty(redis: Any, spec: SnapshotSpec[T]) -> T:
    try:
        data = await load_snapshot(redis, spec)
        return data if data is not None else spec.empty_factory()
    except Exception:
        logger.warning("[盘前快照] Redis 不可用或快照读取失败：%s", spec.name, exc_info=True)
        return spec.empty_factory()


async def save_snapshot(redis: Any, spec: SnapshotSpec[T], data: T) -> None:
    now = datetime.now(tz=UTC).isoformat()
    payload = json.dumps(
        {
            "name": spec.name,
            "updated_at": now,
            "data": to_jsonable(data),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    tmp_key = f"{spec.redis_key}:tmp:{uuid4().hex}"
    await redis.set(tmp_key, payload, ex=SNAPSHOT_RETAIN_SECONDS)
    await redis.rename(tmp_key, spec.redis_key)
    await redis.expire(spec.redis_key, SNAPSHOT_RETAIN_SECONDS)


async def acquire_snapshot_lock(redis: Any, name: str, ttl_seconds: int) -> str | None:
    token = uuid4().hex
    ok = await redis.set(f"{SNAPSHOT_LOCK_PREFIX}{name}", token, nx=True, ex=ttl_seconds)
    return token if ok else None


async def release_snapshot_lock(redis: Any, name: str, token: str) -> None:
    await redis.eval(_RELEASE_LOCK_SCRIPT, 1, f"{SNAPSHOT_LOCK_PREFIX}{name}", token)
