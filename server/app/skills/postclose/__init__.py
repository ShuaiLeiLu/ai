"""盘后 skill 集合。"""
from __future__ import annotations

from app.skills.registry import SkillRegistry


def register_all(registry: SkillRegistry) -> None:
    from app.skills.postclose.single_trade import SingleTradeSkill
    from app.skills.postclose.pnl_attribution import PnlAttributionSkill
    from app.skills.postclose.alpha_analysis import AlphaAnalysisSkill
    from app.skills.postclose.opportunity_cost import OpportunityCostSkill
    from app.skills.postclose.daily_coach import DailyCoachSkill

    registry.register(SingleTradeSkill())
    registry.register(PnlAttributionSkill())
    registry.register(AlphaAnalysisSkill())
    registry.register(OpportunityCostSkill())
    registry.register(DailyCoachSkill())

    # Phase 4 可选
    try:
        from app.skills.postclose.pattern_match import PatternMatchSkill
        from app.skills.postclose.thesis_scorecard import ThesisScorecardSkill
        registry.register(PatternMatchSkill())
        registry.register(ThesisScorecardSkill())
    except (ImportError, AttributeError):
        pass


DAILY_REVIEW_SKILL_NAMES = [
    "pnl_attribution",
    "alpha_analysis",
    "opportunity_cost",
    "daily_coach",
]
