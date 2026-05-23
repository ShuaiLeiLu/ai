"""Skill 框架 —— 把分析拆成可组合的独立单元。

每个 skill 是一个 Python 类,负责取数据 → 调用 LLM → 输出结构化结果。
Orchestrator 按依赖顺序串联 skill,前一个 skill 的 narrative/structured
可作为下一个 skill 的输入。

设计动机:把过去单次大 LLM 调用拆成多个小调用,每个调用专注一件事,
让 prompt 可以写得更深、更 opinionated,同时支持 SSE 流式输出。
"""
from app.skills.base import (
    SkillBase,
    SkillContext,
    SkillEvent,
    SkillEventType,
    SkillResult,
)
from app.skills.orchestrator import SkillOrchestrator
from app.skills.registry import SkillRegistry, get_skill_registry

__all__ = [
    "SkillBase",
    "SkillContext",
    "SkillEvent",
    "SkillEventType",
    "SkillResult",
    "SkillOrchestrator",
    "SkillRegistry",
    "get_skill_registry",
]
