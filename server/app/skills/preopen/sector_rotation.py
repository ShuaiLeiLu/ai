"""SectorRotationSkill —— 板块轮动方向判断。"""
from __future__ import annotations

from app.integrations.akshare.client import get_industry_boards, get_sector_fund_flow
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import gather_safe, load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class SectorRotationSkill(SkillBase):
    name = "sector_rotation"
    description = "行业板块涨跌 + 资金流方向,判断今日轮动主线"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        boards, flow = await gather_safe(
            load(get_industry_boards),
            load(get_sector_fund_flow),
        )
        boards = boards or []
        flow = flow or []
        if not boards and not flow:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="行业板块数据未获取,跳过轮动分析。",
                structured={"data_available": False},
            )

        data_text = self._format(boards, flow)
        system = (
            "你是 A 股板块轮动分析师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于行业涨跌 + 资金流方向,给出 300-500 字判断。\n"
            "关键判断:\n"
            "  1) 今日哪个板块是真主线(涨幅 + 主力净流入双高)\n"
            "  2) 哪些是补涨(涨幅高但主力流出 → 散户接盘)\n"
            "  3) 主力调仓方向(从哪个板块流出 → 流入哪个板块)\n"
            "  4) 不同时间维度的强弱切换(今日强 vs 近期强)\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"main_sector": "<板块名>",\n'
            ' "supplementary_sectors": [...],\n'
            ' "fund_rotation": "<从X流出到Y>",\n'
            ' "warning_sectors": [...]}\n'
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
    def _format(boards, flow) -> str:
        # 涨幅榜前 10 + 跌幅榜后 5
        sorted_up = sorted(boards, key=lambda b: b.change_pct, reverse=True)[:10]
        sorted_down = sorted(boards, key=lambda b: b.change_pct)[:5]
        up_text = "\n".join(
            f"  - {b.name} {b.change_pct:+.2f}% 净流入:{b.net_inflow:+.2f}亿 "
            f"涨/跌:{b.rise_count}/{b.fall_count} 龙头:{b.leading_stock}({b.leading_stock_pct:+.1f}%)"
            for b in sorted_up
        )
        down_text = "\n".join(
            f"  - {b.name} {b.change_pct:+.2f}% 净流入:{b.net_inflow:+.2f}亿"
            for b in sorted_down
        )
        # 主力资金净流入前 10
        sorted_flow = sorted(
            flow, key=lambda f: f.main_net_inflow, reverse=True,
        )[:10]
        flow_text = "\n".join(
            f"  - {f.name} 涨{f.change_pct:+.2f}% "
            f"主力净流入{f.main_net_inflow/100000000:+.2f}亿 占比{f.main_net_pct:+.2f}%"
            for f in sorted_flow
        ) or "  (无)"

        return (
            f"=== 行业涨幅榜(前 10)===\n{up_text}\n\n"
            f"=== 行业跌幅榜(后 5)===\n{down_text}\n\n"
            f"=== 主力资金净流入榜(前 10)===\n{flow_text}"
        )
