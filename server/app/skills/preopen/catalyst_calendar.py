"""CatalystCalendarSkill —— 今日财报披露 / 解禁 / 新股 / 政策窗口。"""
from __future__ import annotations

from app.integrations.akshare.client import (
    get_earnings_calendar,
    get_ipo_calendar,
    get_unlock_calendar,
)
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import gather_safe, load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class CatalystCalendarSkill(SkillBase):
    name = "catalyst_calendar"
    description = "今日财报披露 / 解禁 / 新股申购等关键日历事件"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        earnings, unlock, ipo = await gather_safe(
            load(get_earnings_calendar, ctx.trade_date),
            load(get_unlock_calendar, ctx.trade_date),
            load(get_ipo_calendar),
        )
        earnings = earnings or []
        unlock = unlock or []
        ipo = ipo or []

        if not earnings and not unlock and not ipo:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="今日无重要日历事件。",
                structured={"events": []},
            )

        data_text = self._format(earnings, unlock, ipo)
        system = (
            "你是 A 股事件驱动分析师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于今日财报披露 / 解禁 / 新股名单,给出 200-400 字判断。\n"
            "重点:\n"
            "  1) 大额解禁名单 → 短期承压标的(>3% 占总股本就值得提醒)\n"
            "  2) 财报披露中的预增/预减 → 短期机会或风险\n"
            "  3) 新股申购日程 → 资金分流影响\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"must_watch": [{"symbol": "...", "reason": "..."}],\n'
            ' "risk_alerts": [...]}\n'
            "```"
        )

        try:
            reply = await get_llm_client().chat(
                [LLMMessage("system", system), LLMMessage("user", data_text)],
                profile=self.model_profile, max_tokens=1200,
            )
        except Exception as exc:
            return SkillResult(skill_name=self.name, success=False, error=str(exc))

        narrative, structured = split_narrative_and_json(reply)
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )

    @staticmethod
    def _format(earnings, unlock, ipo) -> str:
        e_text = "\n".join(
            f"  - {e.name}({e.symbol}) {e.detail}" for e in earnings[:15]
        ) or "  (无)"
        u_text = "\n".join(
            f"  - {u.name}({u.symbol}) {u.detail}" for u in unlock[:15]
        ) or "  (无)"
        i_text = "\n".join(
            f"  - {i.name}({i.symbol}) 申购日 {i.trade_date} {i.detail}"
            for i in ipo[:10]
        ) or "  (无)"
        return (
            f"=== 今日财报披露 ===\n{e_text}\n\n"
            f"=== 今日解禁名单 ===\n{u_text}\n\n"
            f"=== 近期新股申购 ===\n{i_text}"
        )
