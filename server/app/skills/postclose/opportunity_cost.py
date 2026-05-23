"""OpportunityCostSkill —— 候选池机会成本分析。

如果策略当日候选了 A/B/C,只买了 A,那么 B/C 实际表现是机会成本。
依赖 ctx.extra["candidate_pool"] 传入候选池列表,以及今日成交记录。
若候选池数据不可得,skill 优雅降级。
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.client import (
    get_stock_quote_by_symbols,
    run_sync,
)
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.trading import TradeRecord
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class OpportunityCostSkill(SkillBase):
    name = "opportunity_cost"
    description = "对照当日候选池未买入标的的实际表现,评估机会成本"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        account_id = ctx.extra.get("account_id")
        session: AsyncSession | None = ctx.extra.get("session")
        candidate_pool: list[dict] | None = ctx.extra.get("candidate_pool")
        if not account_id or session is None:
            return SkillResult(
                skill_name=self.name, success=False,
                error="缺少 account_id 或 session",
            )
        if not candidate_pool:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="未提供当日候选池数据,跳过机会成本分析。",
                structured={"data_available": False},
            )

        # 取当日实际买入的 symbol
        trades_q = await session.execute(
            select(TradeRecord.symbol).where(
                TradeRecord.account_id == account_id,
                TradeRecord.side == "buy",
            )
        )
        bought_symbols = {row[0] for row in trades_q.all()}
        unbought = [
            c for c in candidate_pool
            if c.get("symbol") not in bought_symbols
        ]

        if not unbought:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="候选池全部已买入,无机会成本可对照。",
                structured={"data_available": True, "unbought_count": 0},
            )

        symbols = [c["symbol"] for c in unbought if c.get("symbol")][:20]
        quotes = await run_sync(get_stock_quote_by_symbols, symbols)
        comparison = []
        for c in unbought[:20]:
            sym = c.get("symbol")
            q = quotes.get(sym) if sym else None
            if q is None:
                continue
            comparison.append({
                "symbol": sym,
                "name": c.get("name") or q.name,
                "candidate_reason": c.get("reason", "-"),
                "actual_change_pct": q.change_pct,
            })

        if not comparison:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="无法获取未买入候选股行情,跳过分析。",
                structured={"data_available": False},
            )

        data_text = "\n".join(
            f"  - {c['name']}({c['symbol']}) 候选原因:{c['candidate_reason']} "
            f"实际涨跌:{c['actual_change_pct']:+.2f}%"
            for c in comparison
        )

        system = (
            "你是组合选股质量评估师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于当日候选池中未买入的标的实际表现,评估选股逻辑。\n"
            "回答:\n"
            "  1) 候选池里跑得最好的票是哪只,涨多少?如果当时买它会怎样?\n"
            "  2) 选股逻辑是否有缺陷?(例如总错过涨幅最大的)\n"
            "  3) 是单次运气还是系统性偏差?\n"
            "输出 300-500 字。\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"best_unbought": "<symbol+chg>",\n'
            ' "average_unbought_chg": <数值>,\n'
            ' "selection_quality": "good|average|poor",\n'
            ' "improvement_points": [...]}\n'
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
        avg = sum(c["actual_change_pct"] for c in comparison) / len(comparison)
        structured.setdefault("average_unbought_chg", round(avg, 2))
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )
