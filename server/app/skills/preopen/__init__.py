"""盘前 skill 集合。"""
from __future__ import annotations

from app.skills.registry import SkillRegistry


def register_all(registry: SkillRegistry) -> None:
    """把所有盘前 skill 注册到 registry。

    分两层注册:数据型(返回 narrative + structured)→ 综合型(吃前者输出)。
    """
    # 数据层
    from app.skills.preopen.limit_up_structure import LimitUpStructureSkill
    registry.register(LimitUpStructureSkill())

    # Phase 2 数据 skill(可选,失败不阻断)
    for module_name, class_name in [
        ("overseas_market", "OverseasMarketSkill"),
        ("capital_flow", "CapitalFlowSkill"),
        ("longhubang", "LonghubangSkill"),
        ("sector_rotation", "SectorRotationSkill"),
        ("news_catalyst", "NewsCatalystSkill"),
        ("catalyst_calendar", "CatalystCalendarSkill"),
        ("index_technical", "IndexTechnicalSkill"),
    ]:
        try:
            module = __import__(
                f"app.skills.preopen.{module_name}",
                fromlist=[class_name],
            )
            skill_cls = getattr(module, class_name)
            registry.register(skill_cls())
        except (ImportError, AttributeError):
            # Phase 2 未就绪时不阻断 Phase 1
            pass

    # 反思层
    from app.skills.preopen.yesterday_review import YesterdayReviewSkill
    registry.register(YesterdayReviewSkill())

    # 综合层
    from app.skills.preopen.main_thesis import MainThesisSkill
    registry.register(MainThesisSkill())


# Phase 1 必跑的盘前 skill 顺序(供 router 直接拼装 orchestrator)
PHASE1_SKILL_NAMES = [
    "limit_up_structure",
    "yesterday_review",
    "main_thesis",
]

# 完整盘前 skill 名(Phase 2 全部上线后启用)
FULL_PREOPEN_SKILL_NAMES = [
    "overseas_market",
    "capital_flow",
    "longhubang",
    "limit_up_structure",
    "sector_rotation",
    "news_catalyst",
    "catalyst_calendar",
    "index_technical",
    "yesterday_review",
    "main_thesis",
]
