"""MainThesisSkill —— 盘前主线综合判断(synthesis 类)。

业界 morning-note 关键原则:
  1) Opinionated:必须有立场,不允许骑墙
  2) Falsifiable:必须给反方信号(可证伪)
  3) Tight format with high density:5 段结构紧凑但有判断力

吃前置 skill:
  - limit_up_structure(必)
  - yesterday_review(必,即使是"首日运行"也要带上)
  - 其他 Phase 2 数据 skill(optional)

输出:
  narrative: 1500-2500 字 markdown(走 LLM 流式输出)
  structured: {
    "bias": "bullish|bearish|mixed|retreat",
    "core_thesis": "...",
    "falsification_signals": [...],
    "intraday_checkpoints": [...],
    "operation_discipline": [...]
  }
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import (
    A_SHARE_CONTEXT,
    SYNTHESIS_SKILL_GUARDRAILS,
)

logger = logging.getLogger(__name__)

# 完整盘前 skill 名称(Phase 2 上线后会扩展),用于动态拼装前置输出
_UPSTREAM_SKILLS_NAMES = [
    "overseas_market",
    "capital_flow",
    "longhubang",
    "limit_up_structure",
    "sector_rotation",
    "news_catalyst",
    "catalyst_calendar",
    "index_technical",
    "yesterday_review",
]


class MainThesisSkill(SkillBase):
    name = "main_thesis"
    description = "盘前主线综合判断,opinionated + falsifiable"
    # 至少要 limit_up_structure + yesterday_review
    depends_on = ["limit_up_structure", "yesterday_review"]
    # 其他都是可选
    optional_deps = [
        "overseas_market",
        "capital_flow",
        "longhubang",
        "sector_rotation",
        "news_catalyst",
        "catalyst_calendar",
        "index_technical",
    ]
    model_profile = "synthesis"

    # ── 非流式实现:走 _execute_stream 累积 ──
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

    # ── 流式实现 ──
    async def _execute_stream(
        self, ctx: SkillContext,
    ) -> AsyncIterator[str | SkillResult]:
        upstream_dump = self._build_upstream_dump(ctx)
        system = self._build_system_prompt()
        user_msg = (
            f"=== 今日交易日:{ctx.trade_date.isoformat()} ===\n\n"
            f"=== 各路研究员的输入(必须基于这些事实) ===\n\n"
            f"{upstream_dump}\n\n"
            "请你按照系统指令的 5 段结构,写一份 1500-2500 字的盘前主线内参。"
        )

        accumulated: list[str] = []
        try:
            async for chunk in get_llm_client().chat_stream(
                [
                    LLMMessage("system", system),
                    LLMMessage("user", user_msg),
                ],
                profile=self.model_profile,
                max_tokens=4500,
            ):
                accumulated.append(chunk)
                yield chunk
        except Exception as exc:
            logger.exception("MainThesisSkill 流式调用失败")
            yield SkillResult(
                skill_name=self.name,
                success=False,
                error=f"LLM 流式调用失败: {exc}",
                narrative="".join(accumulated),
            )
            return

        full_text = "".join(accumulated)
        narrative, structured = split_narrative_and_json(full_text)
        # 兜底:即使没解析到 JSON,也提供基础字段
        structured.setdefault("bias", "mixed")
        structured.setdefault("falsification_signals", [])
        structured.setdefault("intraday_checkpoints", [])
        structured.setdefault("operation_discipline", [])

        yield SkillResult(
            skill_name=self.name,
            success=True,
            narrative=narrative or full_text,
            structured=structured,
        )

    @staticmethod
    def _build_system_prompt() -> str:
        return (
            "你是某券商首席策略分析师,主持每日 8:30 晨会。\n\n"
            f"{A_SHARE_CONTEXT}\n\n"
            f"{SYNTHESIS_SKILL_GUARDRAILS}\n\n"
            "你下属的研究员已经提交了各自的分析(外盘/期指/资金面/龙虎榜/涨停结构/"
            "板块/新闻/技术面/昨日反思)。你的任务是把这些信息整合成一份**有立场的**"
            "盘前主线内参,1500-2500 字。\n\n"
            "结构(严格按此分段):\n"
            "## 一、今日核心矛盾\n"
            "  一句话点出今天最关键的分歧或共振点(不要写『市场存在不确定性』这种废话)。\n\n"
            "## 二、主线判断\n"
            "  明确给出:今日交易主线是哪一个,bullish 还是 bearish,接力还是切换还是退潮。\n"
            "  必须有逻辑链,数字要溯源(指出来自哪个研究员)。\n\n"
            "## 三、反方观点(可证伪信号)\n"
            "  必须列 2-4 条:如果你的判断错了,会在什么具体数据/事件上确认错误。\n"
            "  这是 thesis 的可证伪性,没有这部分等于没判断。\n\n"
            "## 四、盘中验证点\n"
            "  分三个时间窗:\n"
            "  - 09:25-09:40 竞价/早盘 → 看什么具体信号\n"
            "  - 10:30 之前 → 板块共振是否成立\n"
            "  - 14:00 后尾盘 → 主线是否守住\n\n"
            "## 五、操作纪律\n"
            "  给研究员的具体动作(不是『控制风险』这种套话)。\n"
            "  例如:\n"
            "    - 若 09:30 涨停数 < N 家,降仓至 X%\n"
            "    - 若 XX 板块龙头炸板,优先减持同板块持仓\n\n"
            "最后(在 markdown 之外)附 JSON 摘要:\n"
            "```json\n"
            "{\n"
            '  "bias": "bullish|bearish|mixed|retreat",\n'
            '  "core_thesis": "<一句话主线>",\n'
            '  "falsification_signals": ["..."],\n'
            '  "intraday_checkpoints": ["...", "..."],\n'
            '  "operation_discipline": ["...", "..."]\n'
            "}\n"
            "```"
        )

    @staticmethod
    def _build_upstream_dump(ctx: SkillContext) -> str:
        """把所有上游 skill 的 narrative 拼成一段,按 markdown 分小节。"""
        chunks: list[str] = []
        for skill_name in _UPSTREAM_SKILLS_NAMES:
            result = ctx.get(skill_name)
            if not result or not result.success:
                continue
            narrative = (result.narrative or "").strip()
            structured = result.structured or {}
            if not narrative and not structured:
                continue
            chunks.append(
                f"### 来自 [{skill_name}]\n"
                f"{narrative}\n\n"
                f"(结构化摘要:{structured})"
            )
        return "\n\n---\n\n".join(chunks) if chunks else "(无前置 skill 输出)"
