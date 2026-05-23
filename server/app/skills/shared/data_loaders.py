"""公共数据采集函数(对 akshare client 的薄包装)。

把 skill 用到的常见数据获取放在这里,避免每个 skill 各自处理 run_sync。
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.integrations.akshare.client import run_sync

T = TypeVar("T")


async def load(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """异步包装同步 akshare 调用,与 client.run_sync 一致。"""
    return await run_sync(fn, *args, **kwargs)


async def gather_safe(*coros: Awaitable[Any]) -> list[Any]:
    """并发执行多个数据 coroutine,失败项以 None 占位,不抛异常。"""
    import asyncio

    results = await asyncio.gather(*coros, return_exceptions=True)
    return [r if not isinstance(r, Exception) else None for r in results]
