"""CapitalFlowSkill —— 北向资金 + 两融余额判断机构/散户动向。"""
from __future__ import annotations

from app.integrations.akshare.client import get_margin_balance, get_northbound_flow
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class CapitalFlowSkill(SkillBase):
    name = "capital_flow"
    description = "北向资金 + 两融余额组合判断今日资金面"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        northbound = await load(get_northbound_flow)
        margin = await load(get_margin_balance)

        if northbound is None and margin is None:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="北向资金和两融余额数据均未获取,无法判断资金面。",
                structured={"data_available": False},
            )

        data_text = self._format(northbound, margin)
        system = (
            "你是 A 股资金面分析师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于北向资金净流入 + 两融余额,给出 200-300 字判断。\n"
            "关键判断点:\n"
            "  1) 北向资金代表的外资/机构动向(净流入 vs 净流出 vs 大幅波动)\n"
            "  2) 两融余额代表的散户/游资杠杆情绪(攀升 vs 回落)\n"
            "  3) 两者背离时尤其要点出来(机构跑,散户加杠杆 → 短期顶部信号)\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"institution_bias": "bullish|bearish|neutral",\n'
            ' "retail_leverage": "rising|falling|stable",\n'
            ' "divergence": <bool>,\n'
            ' "key_signals": [...]}\n'
            "```"
        )

        try:
            reply = await get_llm_client().chat(
                [LLMMessage("system", system), LLMMessage("user", data_text)],
                profile=self.model_profile, max_tokens=900,
            )
        except Exception as exc:
            return SkillResult(skill_name=self.name, success=False, error=str(exc))

        narrative, structured = split_narrative_and_json(reply)
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )

    @staticmethod
    def _format(northbound, margin) -> str:
        n_text = "(未获取)" if northbound is None else (
            f"  日期:{northbound.trade_date}\n"
            f"  沪股通净流入:{northbound.sh_net_amount:+.2f} 亿\n"
            f"  深股通净流入:{northbound.sz_net_amount:+.2f} 亿\n"
            f"  合计:{northbound.total_net:+.2f} 亿"
        )
        m_text = "(未获取)" if margin is None else (
            f"  日期:{margin.trade_date}\n"
            f"  融资余额:{margin.financing_balance:.0f} 亿\n"
            f"  融券余额:{margin.securities_balance:.0f} 亿\n"
            f"  两融合计:{margin.total_balance:.0f} 亿"
        )
        return f"=== 北向资金(昨日)===\n{n_text}\n\n=== 两融余额(最近一日)===\n{m_text}"
