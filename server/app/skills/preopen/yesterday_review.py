"""YesterdayReviewSkill —— 自我反思:昨日判断 vs 今日实际。

为什么这个 skill 是关键:
  业界 morning-note 原则:"Own mistakes in subsequent notes for credibility"
  现在的盘前 AI 从不回看自己昨天的判断,导致永远是"事后诸葛亮"。
  这个 skill 强制 AI 每天写一段"昨天我判断 X,今天实际 Y,误差在 Z"。

输入(由 ctx.extra 提供):
  - session: AsyncSession,用来查 PreopenAiDigest
  - today_data_text: 今日实际开盘/盘前数据,由 limit_up_structure 等前置 skill 提供

策略:
  - 假期/停盘后首日:取最近一个有 digest 的交易日比对(不是"昨日")
  - 首次运行时无任何历史 digest:输出"首日运行,无对照",不阻断主流程
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.preopen import PreopenAiDigest
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT

logger = logging.getLogger(__name__)


class YesterdayReviewSkill(SkillBase):
    name = "yesterday_review"
    description = "对比昨日盘前判断与今日实际走势,生成自我反思"
    # 强依赖 limit_up_structure 取今日实际数据
    depends_on = ["limit_up_structure"]
    # 这些信号若有更好,缺也不阻断
    optional_deps = [
        "overseas_market",
        "capital_flow",
        "longhubang",
    ]
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        session: AsyncSession | None = ctx.extra.get("session")
        if session is None:
            return SkillResult(
                skill_name=self.name,
                success=True,
                narrative="未提供数据库会话,跳过自我反思。",
                structured={"status": "skipped_no_session"},
            )

        previous = await self._load_previous_digest(session, ctx.trade_date)
        if previous is None:
            return SkillResult(
                skill_name=self.name,
                success=True,
                narrative=(
                    "首次运行,无昨日盘前判断可对照。后续每个交易日生成的 "
                    "PreopenAiDigest 会被这个 skill 自动召回。"
                ),
                structured={"status": "first_run"},
            )

        today_actual = self._collect_today_actual(ctx)
        previous_thesis = previous.main_thesis_md or ""
        previous_signals = previous.falsification_signals or []
        previous_bias = previous.bias or "未明确"

        system = (
            "你是 A 股盘前分析师,但今天要做的不是分析市场,而是 review 你自己。\n\n"
            f"{A_SHARE_CONTEXT}\n\n"
            "我会给你两份材料:\n"
            "  1) 昨日(或上一个交易日)你发的盘前主线判断 + 当时给出的可证伪信号\n"
            "  2) 今日实际市场表现\n\n"
            "你要写一段 500-800 字的自我反思,分三部分:\n"
            "  ### 一、判断对的部分\n"
            "    引用昨日具体判断 → 引用今日具体数据 → 说明对在哪\n"
            "  ### 二、判断错的部分(诚实承认,不要找理由)\n"
            "    引用昨日具体判断 → 引用今日具体数据 → 说明错在哪\n"
            "  ### 三、学到的东西\n"
            "    1-2 条具体的、可操作的改进点,不要写『加强学习』这种废话\n\n"
            "纪律:\n"
            "  - 不允许夸大对的部分,也不要回避错的部分\n"
            "  - 必须引用具体数字(涨停数、最高连板、北向资金、指数涨跌)\n"
            "  - 如果当时给的可证伪信号被触发了,必须明确指出\n"
            "  - 末尾附 JSON 摘要:\n"
            "    {\"correctness\": \"correct|partial|wrong\", \n"
            "     \"key_errors\": [...], \n"
            "     \"falsification_triggered\": [...]}\n"
        )

        user_msg = (
            f"=== 上一个有效交易日 {previous.trade_date.isoformat()} 的盘前判断 ===\n"
            f"主线方向:{previous_bias}\n\n"
            f"完整主线内参:\n{previous_thesis}\n\n"
            f"当时给出的可证伪信号:\n"
            + ("\n".join(f"  - {s}" for s in previous_signals)
               if previous_signals
               else "  (当时未明确给出)")
            + f"\n\n=== 今日({ctx.trade_date.isoformat()}) 实际数据 ===\n"
            + today_actual
        )

        try:
            reply = await get_llm_client().chat(
                [
                    LLMMessage("system", system),
                    LLMMessage("user", user_msg),
                ],
                profile=self.model_profile,
                max_tokens=2000,
            )
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                success=False,
                error=f"LLM 调用失败: {exc}",
            )

        narrative, structured = split_narrative_and_json(reply)
        structured.setdefault("previous_trade_date", previous.trade_date.isoformat())
        return SkillResult(
            skill_name=self.name,
            success=True,
            narrative=narrative or reply,
            structured=structured,
        )

    @staticmethod
    async def _load_previous_digest(
        session: AsyncSession, today: date,
    ) -> PreopenAiDigest | None:
        """取今日之前最近一份 digest。

        实现:`trade_date < today` 倒序取第一条。
        这样自动覆盖"假期/停盘后首日 → 上一个交易日"的场景。
        """
        stmt = (
            select(PreopenAiDigest)
            .where(PreopenAiDigest.trade_date < today)
            .order_by(PreopenAiDigest.trade_date.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    def _collect_today_actual(ctx: SkillContext) -> str:
        """从前置 skill 输出汇总"今日实际数据"文本块。"""
        parts: list[str] = []

        lu = ctx.get_structured("limit_up_structure")
        if lu:
            parts.append(
                "[今日盘面结构(来自 limit_up_structure)]\n"
                f"  涨停 {lu.get('limit_up_count', '-')} 家 / "
                f"跌停 {lu.get('limit_down_count', '-')} 家\n"
                f"  最高连板 {lu.get('leader_consecutive', '-')} 板\n"
                f"  情绪周期判断 {lu.get('cycle_phase', '-')}\n"
                f"  关键信号 {lu.get('key_signals', [])}"
            )

        for opt_skill in ("overseas_market", "capital_flow", "longhubang"):
            data = ctx.get_structured(opt_skill)
            if data:
                parts.append(
                    f"[{opt_skill}]\n  " +
                    "\n  ".join(f"{k}: {v}" for k, v in data.items()
                                if not isinstance(v, (list, dict)))
                )

        return "\n\n".join(parts) if parts else "(前置 skill 未提供今日数据)"
