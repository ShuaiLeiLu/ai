"""PatternMatchSkill —— 历史复盘 RAG 匹配。

用当日复盘要点的 embedding 检索近 30 天相似的 daily_review_reports,
让 daily_coach 能识别"这次错误是不是同一个模式在重演"。

依赖:
  - daily_review_reports 表已写入 embedding(由 Phase 4 落库逻辑回填)
  - LLM profile 支持 embedding 接口(走 OpenAI 兼容 /v1/embeddings)
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.trading import DailyReviewReport
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS

logger = logging.getLogger(__name__)


async def embed_text(text: str) -> list[float] | None:
    """调用 OpenAI 兼容 /v1/embeddings 接口生成 embedding。

    模型固定 text-embedding-3-small(1536 维),走 default profile。
    """
    settings = get_settings()
    base_url = settings.openai_base_url
    api_key = settings.openai_api_key
    if not base_url or not api_key:
        logger.warning("embed_text: openai_base_url/api_key 未配置")
        return None
    try:
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30, connect=10),
        ) as client:
            resp = await client.post(
                "/v1/embeddings",
                json={"input": text[:8000], "model": "text-embedding-3-small"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data["data"][0]["embedding"]
    except Exception:
        logger.exception("embed_text 失败")
        return None


class PatternMatchSkill(SkillBase):
    name = "pattern_match"
    description = "当日复盘要点 → 近 30 天相似复盘 RAG 匹配"
    depends_on = ["pnl_attribution"]
    optional_deps = ["alpha_analysis"]
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        session: AsyncSession | None = ctx.extra.get("session")
        researcher_id = ctx.researcher_id
        if session is None or not researcher_id:
            return SkillResult(
                skill_name=self.name, success=False,
                error="缺少 session 或 researcher_id",
            )

        # 把当日 pnl_attribution + alpha_analysis 拼成 query
        query_parts: list[str] = []
        for name in ("pnl_attribution", "alpha_analysis"):
            r = ctx.get(name)
            if r and r.success and r.narrative:
                query_parts.append(r.narrative[:1500])
        query = "\n\n".join(query_parts)
        if not query:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="当日复盘要点不足,跳过 RAG 匹配。",
                structured={"matched": 0},
            )

        query_emb = await embed_text(query)
        if query_emb is None:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="embedding 不可用,跳过 RAG 匹配。",
                structured={"matched": 0},
            )

        # 取近 30 天的复盘报告,Python 端算余弦相似度 top-3
        # (服务器未装 pgvector,用 JSONB 存 embedding,数据量小性能不是问题)
        cutoff = ctx.trade_date - timedelta(days=30)
        stmt = (
            select(DailyReviewReport)
            .where(
                DailyReviewReport.researcher_id == researcher_id,
                DailyReviewReport.trade_date < ctx.trade_date,
                DailyReviewReport.trade_date >= cutoff,
                DailyReviewReport.embedding.isnot(None),
            )
        )
        all_rows = (await session.execute(stmt)).scalars().all()
        if not all_rows:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="近 30 天无可对照的历史复盘。",
                structured={"matched": 0},
            )

        # 计算与每条历史复盘的余弦相似度并取 top-3
        scored: list[tuple[float, Any]] = []
        for row in all_rows:
            try:
                sim = _cosine_similarity(query_emb, row.embedding)
            except Exception:
                continue
            scored.append((sim, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        top3 = scored[:3]
        if not top3:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="历史复盘 embedding 不可用,跳过 RAG。",
                structured={"matched": 0},
            )

        data_text = "\n\n".join(
            f"=== {row.trade_date.isoformat()} (相似度 {sim:.3f}) ===\n"
            f"alpha vs 指数:{row.alpha_vs_index:+.2f}%\n\n"
            f"{(row.coach_report_md or '')[:1500]}"
            for sim, row in top3
        )

        system = (
            "你是模式识别分析师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:给定研究员今日的复盘要点 + 近期最相似的 3 份历史复盘,\n"
            "判断今天的错误/成功是不是某种模式的重演。\n"
            "输出 200-400 字。\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"pattern_repeated": <bool>,\n'
            ' "pattern_name": "<简短描述>",\n'
            ' "occurred_dates": ["..."]}\n'
            "```"
        )
        user_msg = (
            f"=== 今日复盘要点 ===\n{query}\n\n"
            f"=== 近期最相似的 3 份历史复盘 ===\n{data_text}"
        )

        try:
            reply = await get_llm_client().chat(
                [LLMMessage("system", system), LLMMessage("user", user_msg)],
                profile=self.model_profile, max_tokens=900,
            )
        except Exception as exc:
            return SkillResult(skill_name=self.name, success=False, error=str(exc))

        narrative, structured = split_narrative_and_json(reply)
        structured.setdefault("matched", len(top3))
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """两个向量的余弦相似度,纯 Python 实现(避免引入 numpy 依赖)。"""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
