"""OverseasMarketSkill —— 隔夜外盘 + 期指夜盘融合判断。"""
from __future__ import annotations

from app.integrations.akshare.client import (
    get_futures_night_quotes,
    get_overseas_indices,
)
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class OverseasMarketSkill(SkillBase):
    name = "overseas_market"
    description = "隔夜美股 + 沪深期指夜盘对 A 股竞价的影响判断"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        indices = await load(get_overseas_indices)
        futures = await load(get_futures_night_quotes)

        if not indices and not futures:
            return SkillResult(
                skill_name=self.name,
                success=True,
                narrative="隔夜外盘和期指数据均未获取到,无法判断。",
                structured={"bias": "unknown", "data_available": False},
            )

        data_text = self._format(indices, futures)
        system = (
            "你是 A 股策略分析师,专门把隔夜外盘信号翻译成今日 A 股竞价的具体判断。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于隔夜美股 + 沪深期指夜盘,给出 300-500 字判断。必须回答:\n"
            "  1) 今日 A 股竞价大概率怎么走(高开/平开/低开 + 分歧 vs 一致的程度)\n"
            "  2) 受益板块 / 承压板块(具体行业,不要泛泛)\n"
            "  3) 反逻辑信号(如果有,例如纳指跌但费半涨)\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"bias": "bullish|bearish|mixed",\n'
            ' "open_expectation": "<高开|平开|低开>",\n'
            ' "impact_sectors_up": [...],\n'
            ' "impact_sectors_down": [...],\n'
            ' "counter_signals": [...]}\n'
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
    def _format(indices, futures) -> str:
        idx_text = "\n".join(
            f"  - {i.name}({i.symbol}) {i.price:.2f} {i.change_pct:+.2f}%"
            for i in indices
        ) or "  (未获取)"
        fut_text = "\n".join(
            f"  - {f.name}({f.symbol}) {f.price:.1f} {f.change_pct:+.2f}% "
            f"vol={f.volume:.0f} oi={f.open_interest:.0f}"
            for f in futures
        ) or "  (未获取)"
        return (
            f"=== 隔夜美股 ===\n{idx_text}\n\n"
            f"=== 沪深 IF/IH/IC 期指夜盘 ===\n{fut_text}"
        )
