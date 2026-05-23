"""Skill 注册表 —— 按名字查找 skill 实例。"""
from __future__ import annotations

from app.skills.base import SkillBase


class SkillRegistry:
    """全局 skill 注册表。skill 模块在 import 时调用 register() 自我注册。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillBase] = {}

    def register(self, skill: SkillBase) -> SkillBase:
        if skill.name in self._skills:
            raise ValueError(f"skill 重复注册: {skill.name}")
        self._skills[skill.name] = skill
        return skill

    def get(self, name: str) -> SkillBase:
        if name not in self._skills:
            raise KeyError(f"未注册的 skill: {name}")
        return self._skills[name]

    def get_optional(self, name: str) -> SkillBase | None:
        return self._skills.get(name)

    def names(self) -> list[str]:
        return list(self._skills.keys())


_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """获取全局 skill 注册表单例。首次调用会触发子包导入完成自注册。"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
        # 触发 skill 模块导入并自注册
        from app.skills.preopen import register_all as register_preopen
        register_preopen(_registry)
        try:
            from app.skills.postclose import register_all as register_postclose
            register_postclose(_registry)
        except ImportError:
            # postclose 包未就绪时不阻断
            pass
    return _registry
