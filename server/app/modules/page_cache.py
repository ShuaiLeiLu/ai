"""Redis-backed cache helpers for page-facing snapshots."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import UTC, date, datetime
from typing import Any, TypeVar

from pydantic import BaseModel, TypeAdapter

logger = logging.getLogger(__name__)

T = TypeVar("T")

PAGE_CACHE_PREFIX = "page-cache:"


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return _to_jsonable(asdict(value))
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def cache_key(name: str) -> str:
    return f"{PAGE_CACHE_PREFIX}{name}"


async def load_cached(redis: Any, name: str, adapter: TypeAdapter[T]) -> T | None:
    raw = await redis.get(cache_key(name))
    if not raw:
        return None
    try:
        payload = json.loads(raw)
        return adapter.validate_python(payload["data"])
    except Exception:
        logger.warning("[页面缓存] 读取失败：%s", name, exc_info=True)
        return None


async def save_cached(redis: Any, name: str, data: T, *, ttl_seconds: int) -> None:
    payload = json.dumps(
        {
            "name": name,
            "updated_at": datetime.now(UTC).isoformat(),
            "data": _to_jsonable(data),
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    await redis.set(cache_key(name), payload, ex=ttl_seconds)


async def delete_cached(redis: Any, name: str) -> None:
    await redis.delete(cache_key(name))
