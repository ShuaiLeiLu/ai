"""ThesisScorecardSkill —— 研究员判断累积评分卡。

读 researcher_thesis_logs 近 30 天数据,统计:
  - 总判断次数
  - 已评估次数(correctness != pending)
  - correct / partial / wrong 占比
  - 不同 bias 下的准确率
然后让 LLM 给一段 200-400 字的长期能力评估。
"""
from __future__ import annotations

import logging
from collections import Counter
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.researcher import ResearcherThesisLog
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS

logger = logging.getLogger(__name__)


class ThesisScorecardSkill(SkillBase):
    name = "thesis_scorecard"
    description = "研究员近 30 天判断累积评分,长期能力评估"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        session: AsyncSession | None = ctx.extra.get("session")
        researcher_id = ctx.researcher_id
        if session is None or not researcher_id:
            return SkillResult(
                skill_name=self.name, success=False,
                error="缺少 session 或 researcher_id",
            )

        cutoff = ctx.trade_date - timedelta(days=30)
        q = await session.execute(
            select(ResearcherThesisLog)
            .where(
                ResearcherThesisLog.researcher_id == researcher_id,
                ResearcherThesisLog.trade_date >= cutoff,
                ResearcherThesisLog.trade_date < ctx.trade_date,
            )
            .order_by(ResearcherThesisLog.trade_date.desc())
        )
        logs = list(q.scalars().all())
        if not logs:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="近 30 天无判断记录,无法评估累积准确率。",
                structured={"sample_size": 0},
            )

        evaluated = [l for l in logs if l.correctness != "pending"]
        sample_size = len(evaluated)
        if sample_size == 0:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative=f"近 30 天共 {len(logs)} 次判断,均待 T+1 评估。",
                structured={"sample_size": 0, "total": len(logs)},
            )

        correct = sum(1 for l in evaluated if l.correctness == "correct")
        partial = sum(1 for l in evaluated if l.correctness == "partial")
        wrong = sum(1 for l in evaluated if l.correctness == "wrong")
        accuracy = correct / sample_size if sample_size else 0.0

        # 分 bias 统计
        bias_counter: Counter[str] = Counter(l.direction_call for l in evaluated)
        bias_correct: Counter[str] = Counter(
            l.direction_call for l in evaluated if l.correctness == "correct"
        )

        bias_breakdown = "\n".join(
            f"  - {b or '未明确'}: {bias_correct[b]}/{cnt} 准确"
            f" ({(bias_correct[b]/cnt*100 if cnt else 0):.0f}%)"
            for b, cnt in bias_counter.most_common()
        )

        data_text = (
            f"近 30 天判断累积:\n"
            f"  总次数:{len(logs)},已评估:{sample_size}\n"
            f"  正确(correct):{correct}\n"
            f"  部分正确(partial):{partial}\n"
            f"  错误(wrong):{wrong}\n"
            f"  累积准确率:{accuracy*100:.1f}%\n\n"
            f"按 bias 分类:\n{bias_breakdown}\n\n"
            f"近 5 次具体判断:\n"
            + "\n".join(
                f"  - {l.trade_date.isoformat()} bias={l.direction_call} "
                f"结果={l.correctness}"
                for l in logs[:5]
            )
        )

        system = (
            "你是研究员长期能力评估师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于近 30 天累积判断数据,给 200-400 字长期能力评估。\n"
            "回答:\n"
            "  1) 综合准确率水平(< 50% / 50-65% / > 65%)\n"
            "  2) 优势:在哪种行情判断更准(bullish / bearish / neutral)\n"
            "  3) 劣势:在哪种行情容易翻车\n"
            "  4) 建议:基于劣势,具体应该改进什么\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"accuracy_pct": <数值>,\n'
            ' "best_bias": "...",\n'
            ' "worst_bias": "...",\n'
            ' "long_term_improvement": [...]}\n'
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
        structured.setdefault("sample_size", sample_size)
        structured.setdefault("accuracy_pct", round(accuracy * 100, 1))
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )
