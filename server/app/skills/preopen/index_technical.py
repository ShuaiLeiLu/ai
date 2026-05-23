"""IndexTechnicalSkill —— 上证 + 创业板技术位判断。"""
from __future__ import annotations

from app.integrations.akshare.client import get_index_daily_bars
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import gather_safe, load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class IndexTechnicalSkill(SkillBase):
    name = "index_technical"
    description = "上证 + 创业板近 20 日 K 线 → 关键支撑/压力位与量能"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        sh, cyb = await gather_safe(
            load(get_index_daily_bars, "sh000001", 20),
            load(get_index_daily_bars, "sz399006", 20),
        )
        sh = sh or []
        cyb = cyb or []
        if not sh and not cyb:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="指数日线未获取,跳过技术分析。",
                structured={"data_available": False},
            )

        data_text = self._format(sh, cyb)
        system = (
            "你是 A 股指数技术分析师,擅长支撑/压力 + 量能背离判断。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于上证 + 创业板近 20 日 K 线,给出 300-500 字判断。必须包含:\n"
            "  1) 当前价格相对前 20 日的位置(高位/中位/低位)\n"
            "  2) 关键支撑位 / 压力位的具体数值\n"
            "  3) 量能背离(若有)\n"
            "  4) 技术形态(突破 / 跌破 / 震荡 / 假突破)\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"sh_position": "high|mid|low",\n'
            ' "sh_support": <数值>,\n'
            ' "sh_resistance": <数值>,\n'
            ' "cyb_position": "high|mid|low",\n'
            ' "volume_divergence": <bool>,\n'
            ' "key_signals": [...]}\n'
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
    def _format(sh, cyb) -> str:
        def fmt(name: str, bars) -> str:
            if not bars:
                return f"=== {name} ===\n  (未获取)"
            head = "  日期        开        收        高        低     成交量(万)"
            rows = [
                f"  {b.trade_date}  {b.open:8.2f}  {b.close:8.2f}  "
                f"{b.high:8.2f}  {b.low:8.2f}  {b.volume/10000:9.0f}"
                for b in bars
            ]
            return f"=== {name} ===\n{head}\n" + "\n".join(rows)

        return fmt("上证综指 sh000001", sh) + "\n\n" + fmt("创业板指 sz399006", cyb)
