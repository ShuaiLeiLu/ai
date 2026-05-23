"""NewsCatalystSkill —— 新闻催化映射到板块/标的。"""
from __future__ import annotations

from app.integrations.akshare.client import get_live_news_merged
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class NewsCatalystSkill(SkillBase):
    name = "news_catalyst"
    description = "新闻 / 政策 / 公告 → 受影响板块和标的的映射"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        news = await load(get_live_news_merged)
        if not news:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="新闻流为空,跳过催化映射。",
                structured={"data_available": False},
            )

        # 取最新 20 条,带 url
        sample = news[:20]
        data_text = "\n".join(
            f"  [{i+1}] [{n.source}] {n.title}\n      正文:{n.content[:120]}\n"
            f"      链接:{n.url or '(无)'}"
            for i, n in enumerate(sample)
        )

        system = (
            "你是 A 股新闻催化分析师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:从今日 20 条新闻中筛出对 A 股有实质催化的 5-8 条,给出 400-600 字判断。\n"
            "每条催化要做到:\n"
            "  1) 引用原文标题(必须保留原链接以便用户追溯)\n"
            "  2) 映射到具体板块或核心标的(不要泛泛)\n"
            "  3) 判断是利好/利空 + 短期/中期\n"
            "  4) 警惕已被提前消化的旧闻\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"catalysts": [\n'
            '  {"title": "...", "url": "...", "sectors": [...], '
            '"impact": "bullish|bearish", "horizon": "short|mid"}\n'
            ']}\n'
            "```"
        )

        try:
            reply = await get_llm_client().chat(
                [LLMMessage("system", system), LLMMessage("user", data_text)],
                profile=self.model_profile, max_tokens=1500,
            )
        except Exception as exc:
            return SkillResult(skill_name=self.name, success=False, error=str(exc))

        narrative, structured = split_narrative_and_json(reply)
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )
