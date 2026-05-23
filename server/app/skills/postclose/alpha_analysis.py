"""AlphaAnalysisSkill —— vs 大盘 / 板块 alpha 分析。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.client import get_index_daily_bars
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.trading import Position, TradingAccountSnapshot
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class AlphaAnalysisSkill(SkillBase):
    name = "alpha_analysis"
    description = "当日组合相对大盘和板块的 alpha 分析"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        account_id = ctx.extra.get("account_id")
        session: AsyncSession | None = ctx.extra.get("session")
        if not account_id or session is None:
            return SkillResult(
                skill_name=self.name, success=False,
                error="缺少 account_id 或 session",
            )

        snapshot_q = await session.execute(
            select(TradingAccountSnapshot).where(
                TradingAccountSnapshot.account_id == account_id,
                TradingAccountSnapshot.trade_date == ctx.trade_date,
            )
        )
        snapshot = snapshot_q.scalar_one_or_none()

        positions_q = await session.execute(
            select(Position).where(Position.account_id == account_id)
        )
        positions = list(positions_q.scalars().all())

        sh_bars = await load(get_index_daily_bars, "sh000001", 2)
        cyb_bars = await load(get_index_daily_bars, "sz399006", 2)

        sh_chg = 0.0
        cyb_chg = 0.0
        if sh_bars and len(sh_bars) >= 2:
            sh_chg = (sh_bars[-1].close - sh_bars[-2].close) / sh_bars[-2].close * 100
        if cyb_bars and len(cyb_bars) >= 2:
            cyb_chg = (
                (cyb_bars[-1].close - cyb_bars[-2].close) / cyb_bars[-2].close * 100
            )

        # 组合当日涨跌(简化:用 daily_pnl / (total_asset - daily_pnl) 近似)
        if snapshot is None:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="未找到当日账户快照,跳过 alpha 分析。",
                structured={"data_available": False},
            )
        prev_asset = snapshot.total_asset - snapshot.daily_pnl
        portfolio_chg = (
            snapshot.daily_pnl / prev_asset * 100 if prev_asset > 0 else 0.0
        )
        alpha_sh = portfolio_chg - sh_chg
        alpha_cyb = portfolio_chg - cyb_chg

        data_text = (
            f"=== 当日表现 ===\n"
            f"  组合涨幅:{portfolio_chg:+.2f}%  (PnL {snapshot.daily_pnl:+.0f})\n"
            f"  上证综指:{sh_chg:+.2f}%\n"
            f"  创业板指:{cyb_chg:+.2f}%\n"
            f"  alpha(vs 上证):{alpha_sh:+.2f}%\n"
            f"  alpha(vs 创业板):{alpha_cyb:+.2f}%\n\n"
            f"=== 当前持仓 ===\n"
            + (
                "\n".join(
                    f"  - {p.name}({p.symbol}) 浮盈 {p.pnl:+.0f}"
                    for p in positions
                )
                or "  (无)"
            )
        )

        system = (
            "你是组合 alpha 分析师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于组合与大盘/板块的相对收益,给 300-500 字判断。\n"
            "必须回答:\n"
            "  1) 跑赢/跑输大盘多少 alpha\n"
            "  2) 跑赢的原因(选股准 vs 择时好 vs 板块踩对)\n"
            "  3) 跑输的原因(逆势 vs 押错板块 vs 仓位过低)\n"
            "  4) 是 alpha(策略胜利)还是 beta(板块跟涨)\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"alpha_vs_index": <数值>,\n'
            ' "alpha_vs_sector": <数值>,\n'
            ' "is_alpha_or_beta": "alpha|beta|mixed",\n'
            ' "key_reasons": [...]}\n'
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
        structured.setdefault("alpha_vs_index", alpha_sh)
        structured.setdefault("alpha_vs_sector", alpha_cyb)
        structured.setdefault("portfolio_change_pct", portfolio_chg)
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )
