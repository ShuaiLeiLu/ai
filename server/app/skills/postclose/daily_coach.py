"""DailyCoachSkill —— 教练综合复盘(synthesis 类,流式输出)。

吃 pnl_attribution / alpha_analysis / opportunity_cost(+ 可选的 pattern_match
和 thesis_scorecard)的输出,生成一份 1200-2000 字的教练复盘。

不是表扬,是找问题。文风像教练对学员说话。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, SYNTHESIS_SKILL_GUARDRAILS

logger = logging.getLogger(__name__)

_UPSTREAM = [
    "pnl_attribution",
    "alpha_analysis",
    "opportunity_cost",
    "pattern_match",       # Phase 4 可选
    "thesis_scorecard",    # Phase 4 可选
]


class DailyCoachSkill(SkillBase):
    name = "daily_coach"
    description = "教练式当日综合复盘,以『找问题』为主"
    depends_on = ["pnl_attribution", "alpha_analysis"]
    optional_deps = ["opportunity_cost", "pattern_match", "thesis_scorecard"]
    model_profile = "synthesis"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        accumulated: list[str] = []
        final: SkillResult | None = None
        async for item in self._execute_stream(ctx):
            if isinstance(item, SkillResult):
                final = item
            else:
                accumulated.append(item)
        if final:
            return final
        return SkillResult(
            skill_name=self.name,
            success=bool(accumulated),
            narrative="".join(accumulated),
        )

    async def _execute_stream(
        self, ctx: SkillContext,
    ) -> AsyncIterator[str | SkillResult]:
        upstream_dump = self._build_upstream_dump(ctx)
        researcher_name = ctx.extra.get("researcher_name", "未命名研究员")
        system = self._build_system_prompt()
        user_msg = (
            f"研究员:{researcher_name}\n"
            f"交易日:{ctx.trade_date.isoformat()}\n\n"
            f"=== 各路 skill 给出的当日分析 ===\n\n{upstream_dump}\n\n"
            "请按系统指令的 5 段结构,写一份 1200-2000 字的教练复盘。"
        )

        accumulated: list[str] = []
        try:
            async for chunk in get_llm_client().chat_stream(
                [LLMMessage("system", system), LLMMessage("user", user_msg)],
                profile=self.model_profile, max_tokens=4000,
            ):
                accumulated.append(chunk)
                yield chunk
        except Exception as exc:
            logger.exception("DailyCoachSkill 流式调用失败")
            yield SkillResult(
                skill_name=self.name, success=False,
                error=f"LLM 流式调用失败: {exc}",
                narrative="".join(accumulated),
            )
            return

        full_text = "".join(accumulated)
        narrative, structured = split_narrative_and_json(full_text)
        structured.setdefault("key_takeaways", [])
        structured.setdefault("improvement_actions", [])

        yield SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or full_text,
            structured=structured,
        )

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "你是这位研究员的私人教练,每天闭市后给他写一份复盘报告。\n\n"
            f"{A_SHARE_CONTEXT}\n{SYNTHESIS_SKILL_GUARDRAILS}\n\n"
            "复盘原则:\n"
            "  - 不要表扬,要找问题(即使今天赚钱,问题也得指出来)\n"
            "  - 不要套话(『继续保持』『加强学习』这种话禁止出现)\n"
            "  - 改进建议必须具体到行为(例如『明天 09:35 前不开仓』而不是『控制风险』)\n\n"
            "结构(严格按此分段):\n"
            "## 一、今日总结\n"
            "  一句话定性今天:大胜 / 小胜 / 小负 / 大败 / 持平。引用具体数字。\n\n"
            "## 二、关键决策评估\n"
            "  挑出今天 2-3 个关键决策(买/卖/不动),逐一评估:对在哪 / 错在哪。\n\n"
            "## 三、模式识别\n"
            "  今天的成功/失败是不是某种模式的重演?(如果有 pattern_match 输入,引用它)\n\n"
            "## 四、明日改进点\n"
            "  1-2 条具体可执行的改进(精确到行为,不要泛泛)\n\n"
            "## 五、长期能力评估\n"
            "  这位研究员近期表现出的核心优劣势是什么?(如果有 thesis_scorecard 输入,引用它)\n\n"
            "末尾(markdown 之外)附 JSON:\n"
            "```json\n"
            "{\n"
            '  "rating": "big_win|small_win|small_loss|big_loss|flat",\n'
            '  "key_takeaways": ["..."],\n'
            '  "improvement_actions": ["..."],\n'
            '  "pattern_repeated": <bool>\n'
            "}\n"
            "```"
        )

    @staticmethod
    def _build_upstream_dump(ctx: SkillContext) -> str:
        chunks: list[str] = []
        for skill_name in _UPSTREAM:
            result = ctx.get(skill_name)
            if not result or not result.success:
                continue
            chunks.append(
                f"### [{skill_name}]\n{(result.narrative or '').strip()}\n\n"
                f"(结构化:{result.structured})"
            )
        return "\n\n---\n\n".join(chunks) if chunks else "(无前置 skill 输出)"
