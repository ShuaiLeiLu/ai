"""Skill 抽象基类与公共数据结构。"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkillContext:
    """Skill 之间传递的上下文。前置 skill 的输出累积在 outputs 中。"""

    trade_date: date
    researcher_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, "SkillResult"] = field(default_factory=dict)

    def get(self, skill_name: str) -> "SkillResult | None":
        return self.outputs.get(skill_name)

    def get_narrative(self, skill_name: str) -> str:
        result = self.outputs.get(skill_name)
        return result.narrative if result and result.success else ""

    def get_structured(self, skill_name: str) -> dict[str, Any]:
        result = self.outputs.get(skill_name)
        return result.structured if result and result.success else {}


@dataclass
class SkillResult:
    """Skill 的标准输出。"""

    skill_name: str
    success: bool
    structured: dict[str, Any] = field(default_factory=dict)
    narrative: str = ""
    error: str | None = None
    tokens_used: int = 0
    duration_ms: int = 0


class SkillEventType(str, Enum):
    """SSE 事件类型。"""

    STARTED = "started"             # chain 整体启动
    SKILL_STARTED = "skill_started"  # 某个 skill 开始执行
    SKILL_CHUNK = "skill_chunk"      # 流式输出片段(主要用于 synthesis 类)
    SKILL_COMPLETED = "skill_completed"
    SKILL_FAILED = "skill_failed"
    DONE = "done"                    # chain 整体结束


@dataclass
class SkillEvent:
    """Orchestrator 通过 run_stream 输出的事件。"""

    type: SkillEventType
    skill_name: str | None = None
    chunk: str | None = None
    narrative: str | None = None
    structured: dict[str, Any] | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class SkillBase(ABC):
    """所有 skill 的抽象基类。

    子类声明:
      - name              唯一标识(snake_case)
      - description       面向 orchestrator/调试
      - depends_on        强依赖(前置失败则跳过)
      - optional_deps     可选依赖(前置失败仍执行)
      - model_profile     LLM profile,默认 "data"(synthesis 类 skill 应覆盖为 "synthesis")

    实现:
      - _execute(ctx)            必须实现,返回最终 SkillResult
      - _execute_stream(ctx)     可选实现,边产边 yield 文本片段;不实现则降级为
                                 走 _execute 后一次性 yield 全部 narrative
    """

    name: str = ""
    description: str = ""
    depends_on: list[str] = []
    optional_deps: list[str] = []
    model_profile: str = "data"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not cls.name and not getattr(cls, "__abstract__", False):
            raise ValueError(f"{cls.__name__} 必须声明 name 属性")

    @abstractmethod
    async def _execute(self, ctx: SkillContext) -> SkillResult: ...

    async def _execute_stream(
        self, ctx: SkillContext
    ) -> AsyncIterator[str | SkillResult]:
        """默认实现:走 _execute 后整体 yield。

        synthesis 类 skill 可以覆盖此方法,边调 LLMClient.chat_stream 边 yield
        文本片段;最后再 yield 一个 SkillResult 收尾。
        """
        result = await self._execute(ctx)
        if result.success and result.narrative:
            yield result.narrative
        yield result

    async def run(self, ctx: SkillContext) -> SkillResult:
        """非流式入口:统一计时和异常捕获。"""
        started = time.perf_counter()
        try:
            result = await self._execute(ctx)
        except Exception as exc:
            logger.exception("[skill] %s 执行异常", self.name)
            result = SkillResult(
                skill_name=self.name, success=False, error=str(exc),
            )
        result.skill_name = self.name
        result.duration_ms = int((time.perf_counter() - started) * 1000)
        return result

    async def run_stream(
        self, ctx: SkillContext
    ) -> AsyncIterator[str | SkillResult]:
        """流式入口:yield 文本片段,最后一个值是 SkillResult。"""
        started = time.perf_counter()
        last_result: SkillResult | None = None
        try:
            async for item in self._execute_stream(ctx):
                if isinstance(item, SkillResult):
                    last_result = item
                yield item
        except Exception as exc:
            logger.exception("[skill stream] %s 执行异常", self.name)
            last_result = SkillResult(
                skill_name=self.name, success=False, error=str(exc),
            )
            yield last_result
        if last_result is not None:
            last_result.skill_name = self.name
            last_result.duration_ms = int(
                (time.perf_counter() - started) * 1000
            )
