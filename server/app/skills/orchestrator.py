"""Skill 编排器 —— 按依赖顺序执行 skill chain,同层并发,支持 SSE 流式。

执行策略:
  - 拓扑排序:depends_on 形成 DAG,逐层执行
  - 同一层 skill 并发(asyncio.gather)
  - 流式模式下,叶子(synthesis)层串行执行以便顺序 yield chunk;
    其他层仍并发,完成后立刻 yield SKILL_COMPLETED 事件
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from collections.abc import AsyncIterator

from app.skills.base import (
    SkillBase,
    SkillContext,
    SkillEvent,
    SkillEventType,
    SkillResult,
)

logger = logging.getLogger(__name__)


class SkillOrchestrator:
    """串联多个 skill。"""

    def __init__(self, skills: list[SkillBase]) -> None:
        self._skills = {s.name: s for s in skills}
        self._layers = self._topo_layers()

    def _topo_layers(self) -> list[list[SkillBase]]:
        indeg: dict[str, int] = defaultdict(int)
        rev: dict[str, list[str]] = defaultdict(list)
        for skill in self._skills.values():
            for dep in skill.depends_on:
                if dep not in self._skills:
                    raise ValueError(
                        f"skill {skill.name} 依赖了未注册的 skill: {dep}"
                    )
                indeg[skill.name] += 1
                rev[dep].append(skill.name)
            for dep in skill.optional_deps:
                if dep in self._skills:
                    indeg[skill.name] += 1
                    rev[dep].append(skill.name)

        layers: list[list[SkillBase]] = []
        queue: deque[str] = deque(
            name for name in self._skills if indeg[name] == 0
        )
        visited = 0
        while queue:
            layer: list[SkillBase] = []
            for _ in range(len(queue)):
                name = queue.popleft()
                layer.append(self._skills[name])
                visited += 1
                for nxt in rev[name]:
                    indeg[nxt] -= 1
                    if indeg[nxt] == 0:
                        queue.append(nxt)
            layers.append(layer)

        if visited != len(self._skills):
            raise ValueError("skill 依赖存在环,无法拓扑排序")
        return layers

    async def run(self, ctx: SkillContext) -> dict[str, SkillResult]:
        """非流式:逐层执行,把结果写入 ctx.outputs。"""
        for layer in self._layers:
            results = await asyncio.gather(
                *(self._run_one(skill, ctx) for skill in layer),
                return_exceptions=False,
            )
            for skill, result in zip(layer, results, strict=True):
                ctx.outputs[skill.name] = result
                if result.success:
                    logger.info(
                        "[skill] %s ok in %dms", skill.name, result.duration_ms,
                    )
                else:
                    logger.warning(
                        "[skill] %s failed: %s", skill.name, result.error,
                    )
        return ctx.outputs

    async def _run_one(
        self, skill: SkillBase, ctx: SkillContext
    ) -> SkillResult:
        for dep in skill.depends_on:
            dep_result = ctx.outputs.get(dep)
            if not dep_result or not dep_result.success:
                return SkillResult(
                    skill_name=skill.name,
                    success=False,
                    error=f"前置 skill {dep} 未就绪",
                )
        return await skill.run(ctx)

    # ── SSE 流式 ──
    async def run_stream(
        self, ctx: SkillContext
    ) -> AsyncIterator[SkillEvent]:
        """流式执行:逐 skill 推送事件。

        非最后一层:并发执行,完成顺序 yield SKILL_COMPLETED。
        最后一层(假定是 synthesis 单一 skill):走 run_stream 边产边 yield chunk。
        """
        yield SkillEvent(
            type=SkillEventType.STARTED,
            meta={"layers": len(self._layers), "skills": list(self._skills.keys())},
        )
        for layer_idx, layer in enumerate(self._layers):
            is_last_layer = layer_idx == len(self._layers) - 1
            if is_last_layer and len(layer) == 1:
                # 单 skill 最后一层,走流式
                skill = layer[0]
                async for ev in self._run_one_stream(skill, ctx):
                    yield ev
            else:
                # 并发执行,as_completed 顺序推送完成事件
                tasks = {
                    asyncio.create_task(self._run_one(skill, ctx)): skill
                    for skill in layer
                }
                for skill in layer:
                    yield SkillEvent(
                        type=SkillEventType.SKILL_STARTED,
                        skill_name=skill.name,
                    )
                for coro in asyncio.as_completed(tasks.keys()):
                    result = await coro
                    ctx.outputs[result.skill_name] = result
                    if result.success:
                        yield SkillEvent(
                            type=SkillEventType.SKILL_COMPLETED,
                            skill_name=result.skill_name,
                            narrative=result.narrative,
                            structured=result.structured,
                            meta={
                                "duration_ms": result.duration_ms,
                                "tokens_used": result.tokens_used,
                            },
                        )
                    else:
                        yield SkillEvent(
                            type=SkillEventType.SKILL_FAILED,
                            skill_name=result.skill_name,
                            error=result.error,
                        )

        # 汇总 done 事件
        summary = {
            name: {
                "success": r.success,
                "narrative_len": len(r.narrative),
                "duration_ms": r.duration_ms,
                "tokens_used": r.tokens_used,
            }
            for name, r in ctx.outputs.items()
        }
        yield SkillEvent(type=SkillEventType.DONE, meta=summary)

    async def _run_one_stream(
        self, skill: SkillBase, ctx: SkillContext
    ) -> AsyncIterator[SkillEvent]:
        """单 skill 流式包装:检查依赖 → 流式执行 → 累积 narrative → 写 ctx。"""
        for dep in skill.depends_on:
            dep_result = ctx.outputs.get(dep)
            if not dep_result or not dep_result.success:
                fail = SkillResult(
                    skill_name=skill.name,
                    success=False,
                    error=f"前置 skill {dep} 未就绪",
                )
                ctx.outputs[skill.name] = fail
                yield SkillEvent(
                    type=SkillEventType.SKILL_FAILED,
                    skill_name=skill.name,
                    error=fail.error,
                )
                return

        yield SkillEvent(type=SkillEventType.SKILL_STARTED, skill_name=skill.name)
        accumulated_text: list[str] = []
        final_result: SkillResult | None = None
        async for item in skill.run_stream(ctx):
            if isinstance(item, SkillResult):
                final_result = item
                continue
            # 文本片段
            accumulated_text.append(item)
            yield SkillEvent(
                type=SkillEventType.SKILL_CHUNK,
                skill_name=skill.name,
                chunk=item,
            )
        if final_result is None:
            # 兜底:把累积文本组装成 SkillResult
            final_result = SkillResult(
                skill_name=skill.name,
                success=bool(accumulated_text),
                narrative="".join(accumulated_text),
            )
        ctx.outputs[skill.name] = final_result
        if final_result.success:
            yield SkillEvent(
                type=SkillEventType.SKILL_COMPLETED,
                skill_name=skill.name,
                narrative=final_result.narrative,
                structured=final_result.structured,
                meta={
                    "duration_ms": final_result.duration_ms,
                    "tokens_used": final_result.tokens_used,
                },
            )
        else:
            yield SkillEvent(
                type=SkillEventType.SKILL_FAILED,
                skill_name=skill.name,
                error=final_result.error,
            )
