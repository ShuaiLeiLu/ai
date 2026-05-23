"""PnlAttributionSkill —— 当日组合 PnL 归因(选股 / 择时 / 仓位)。"""
from __future__ import annotations

from datetime import datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.trading import (
    Position,
    TradeRecord,
    TradingAccount,
    TradingAccountSnapshot,
)
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class PnlAttributionSkill(SkillBase):
    name = "pnl_attribution"
    description = "当日 PnL 归因到选股/择时/仓位三个维度"
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

        # 取当日成交 + 当前持仓 + 账户快照
        trade_start = datetime.combine(ctx.trade_date, time.min)
        trade_end = datetime.combine(ctx.trade_date, time.max)
        trades_q = await session.execute(
            select(TradeRecord)
            .where(
                TradeRecord.account_id == account_id,
                TradeRecord.created_at >= trade_start,
                TradeRecord.created_at <= trade_end,
            )
            .order_by(TradeRecord.created_at)
        )
        trades = list(trades_q.scalars().all())

        positions_q = await session.execute(
            select(Position).where(Position.account_id == account_id)
        )
        positions = list(positions_q.scalars().all())

        snapshot_q = await session.execute(
            select(TradingAccountSnapshot).where(
                TradingAccountSnapshot.account_id == account_id,
                TradingAccountSnapshot.trade_date == ctx.trade_date,
            )
        )
        snapshot = snapshot_q.scalar_one_or_none()

        if not trades and not positions:
            return SkillResult(
                skill_name=self.name, success=True,
                narrative="今日无成交且无持仓,跳过归因。",
                structured={"data_available": False},
            )

        data_text = self._format(trades, positions, snapshot)
        system = (
            "你是组合归因分析师。\n\n"
            f"{A_SHARE_CONTEXT}\n{DATA_SKILL_GUARDRAILS}\n\n"
            "任务:基于当日所有成交 + 当前持仓 + 账户快照,做 PnL 归因。\n"
            "拆解维度:\n"
            "  1) 选股贡献(买入的股票本身涨跌带来的盈亏)\n"
            "  2) 择时贡献(买入/卖出时点的得失,例如卖飞或抄底)\n"
            "  3) 仓位贡献(整体仓位过高/过低对收益的放大/缩小)\n"
            "输出 300-500 字。\n\n"
            "末尾附 JSON:\n"
            "```json\n"
            '{"total_pnl": <数值>,\n'
            ' "win_count": <int>, "loss_count": <int>,\n'
            ' "best_trade": "<symbol+pnl>",\n'
            ' "worst_trade": "<symbol+pnl>",\n'
            ' "attribution": {"stock_pick": ..., "timing": ..., "sizing": ...}}\n'
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
        structured.setdefault("trade_count", len(trades))
        structured.setdefault("position_count", len(positions))
        return SkillResult(
            skill_name=self.name, success=True,
            narrative=narrative or reply, structured=structured,
        )

    @staticmethod
    def _format(trades, positions, snapshot) -> str:
        t_text = "\n".join(
            f"  - {t.created_at.strftime('%H:%M:%S')} {t.side} "
            f"{t.name}({t.symbol}) {t.quantity}@{t.price:.2f} "
            f"金额{t.quantity * t.price:.0f} 手续费{t.commission:.0f}"
            for t in trades
        ) or "  (今日无成交)"
        p_text = "\n".join(
            f"  - {p.name}({p.symbol}) 持仓 {p.quantity} 成本{p.cost_price:.2f} "
            f"现价{p.current_price:.2f} 浮盈{p.pnl:+.0f}"
            for p in positions
        ) or "  (当前空仓)"
        s_text = "(无快照)" if snapshot is None else (
            f"  总资产 {snapshot.total_asset:.0f}, "
            f"可用 {snapshot.available_cash:.0f}, "
            f"持仓市值 {snapshot.holding_value:.0f}, "
            f"今日 PnL {snapshot.daily_pnl:+.0f}"
        )
        return (
            f"=== 当日成交明细 ===\n{t_text}\n\n"
            f"=== 当前持仓 ===\n{p_text}\n\n"
            f"=== 账户快照 ===\n{s_text}"
        )
