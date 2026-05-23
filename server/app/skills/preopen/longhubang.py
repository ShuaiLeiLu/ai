"""LonghubangSkill —— 龙虎榜游资动向。

A 股短线市场的关键:游资席位驱动情绪股,识别炒股养家/章盟主/孙哥
等知名席位的偏好,能预判今日接力方向。
"""
from __future__ import annotations

from datetime import timedelta

from app.integrations.akshare.client import get_longhubang
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class LonghubangSkill(SkillBase):
    name = "longhubang"
    description = "昨日龙虎榜游资席位 → 今日可能接力方向"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        # 取昨日龙虎榜(今日数据要收盘后才有)
        yesterday = ctx.trade_date - timedelta(days=1)
        items = await load(get_longhubang, yesterday)
        if not items:
            # 再往前 1 天兜底(周一可能拿不到周日,要拿上周五)
            items = await load(get_longhubang, yesterday - timedelta(days=2))

        if not items:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="未获取到龙虎榜数据,跳过游资动向分析。",
                structured={"data_available": False},
            )

        data_text = self._format(items)
        system = (
            "你是 A 股短线游资派分析师,熟悉知名游资席位偏好。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于龙虎榜昨日个股 + 机构买卖明细,给出 300-500 字判断。\n"
            "必须回答:\n"
            "  1) 哪些标的有大额机构买入(机构买入额 > 卖出额 → 中线认可)\n"
            "  2) 哪些是游资接力(净买额大但机构占比低)\n"
            "  3) 推测今日可能继续被接力的方向(行业/概念)\n"
            "  4) 警示:哪些是游资接力后机构跑路(典型出货特征)\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"institution_picks": [...],\n'
            ' "hot_money_picks": [...],\n'
            ' "relay_directions": [...],\n'
            ' "warning_signs": [...]}\n'
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
    def _format(items) -> str:
        # 取净买额排序,机构/游资各列前 8
        institution = sorted(
            items, key=lambda x: x.institution_buy - x.institution_sell, reverse=True,
        )[:8]
        hotmoney = sorted(items, key=lambda x: x.net_amount, reverse=True)[:10]

        ins_text = "\n".join(
            f"  - {i.name}({i.symbol}) 涨{i.change_pct:+.2f}% "
            f"机构净买{(i.institution_buy - i.institution_sell)/10000:.0f}万 "
            f"原因:{i.reason}"
            for i in institution
        ) or "  (无)"
        hm_text = "\n".join(
            f"  - {i.name}({i.symbol}) 涨{i.change_pct:+.2f}% "
            f"龙虎榜净买{i.net_amount/10000:.0f}万 原因:{i.reason}"
            for i in hotmoney
        ) or "  (无)"
        return (
            f"=== 机构净买前 8(可能中线买入)===\n{ins_text}\n\n"
            f"=== 龙虎榜净买前 10(游资合力)===\n{hm_text}"
        )
