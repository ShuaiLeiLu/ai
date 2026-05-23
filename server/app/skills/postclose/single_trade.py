"""SingleTradeSkill —— 单笔即时复盘的 SkillBase 包装。

委托给现有 TradingReflectionSkill,保持向后兼容;
但通过 SkillBase 接口暴露,供 daily_coach 编排或 SSE 调用。
"""
from __future__ import annotations

from app.modules.trading.reflection_skill import TradingReflectionSkill
from app.skills.base import SkillBase, SkillContext, SkillResult


class SingleTradeSkill(SkillBase):
    name = "single_trade"
    description = "单笔成交即时复盘(委托 TradingReflectionSkill)"
    depends_on: list[str] = []
    model_profile = "data"

    def __init__(self) -> None:
        self._delegate = TradingReflectionSkill()

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        researcher_name = ctx.extra.get("researcher_name", "未命名研究员")
        researcher_prompt = ctx.extra.get("researcher_prompt", "")
        trade_context = ctx.extra.get("trade_context")
        if not trade_context:
            return SkillResult(
                skill_name=self.name, success=False,
                error="缺少 trade_context,无法复盘",
            )

        try:
            markdown = await self._delegate.build_trade_reflection(
                researcher_name=researcher_name,
                researcher_prompt=researcher_prompt,
                trade_context=trade_context,
                allow_fallback=True,
            )
        except Exception as exc:
            return SkillResult(skill_name=self.name, success=False, error=str(exc))

        return SkillResult(
            skill_name=self.name, success=True,
            narrative=markdown,
            structured={
                "side": trade_context.get("side"),
                "symbol": trade_context.get("symbol"),
                "name": trade_context.get("name"),
                "amount": trade_context.get("amount"),
                "realized_pnl": trade_context.get("realized_pnl"),
            },
        )
