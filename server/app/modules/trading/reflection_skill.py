"""单笔交易即时复盘 skill。

设计原则(2026-05-22 重写):
  - 不是"描述员",是评估这笔交易的教练
  - 必须给得分(1-10) + 核心问题 + 具体次日 if-then 动作
  - 上下文敏感:加载当日同账户其他成交 + 这只票历史成交
  - 失败时返回最小化确认信息,不再写 200 行假分析

为什么之前机械:
  1) fallback 模板覆盖所有字段拼接,谁来都一样
  2) prompt 强制 3 段固定结构,LLM 只能填表
  3) max_tokens=900 太小,无法写深
  4) 永远孤立单笔,看不到组合上下文
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.trading import TradeRecord

logger = logging.getLogger(__name__)


class TradingReflectionSkill:
    """单笔成交即时复盘。

    对外接口保持不变:
      - build_trade_log_title(trade_context) -> str
      - build_trade_reflection(researcher_name, researcher_prompt, trade_context, allow_fallback) -> str

    在 trade_context 中可选传入:
      - session: AsyncSession  → 用于查当日 / 历史成交上下文
      - account_id: str        → 同上
    缺失时优雅降级(无上下文也能跑,但分析没那么深)。
    """

    def build_trade_log_title(self, trade_context: dict[str, Any]) -> str:
        action = "买入操作播报" if trade_context.get("side") == "buy" else "卖出操作播报"
        name = str(trade_context.get("name") or trade_context.get("symbol") or "交易")
        symbol = str(trade_context.get("symbol") or "").strip()
        return f"{action}｜{name}({symbol})" if symbol else f"{action}｜{name}"

    def build_fallback_reflection(
        self,
        *,
        researcher_name: str,
        researcher_prompt: str,
        trade_context: dict[str, Any],
    ) -> str:
        """Legacy synchronous fallback kept for tests and non-LLM callers.

        The main path is `build_trade_reflection`; this method only formats facts
        already present in `trade_context` and never calls external services.
        """
        del researcher_prompt
        side = str(trade_context.get("side") or "buy")
        symbol = str(trade_context.get("symbol") or "-")
        name = str(trade_context.get("name") or symbol)
        price = _fmt_money(trade_context.get("price"))
        cost_price = _fmt_money(trade_context.get("cost_price"))
        realized_pnl = _fmt_money(trade_context.get("realized_pnl"))
        realized_pnl_pct = _fmt_pct(trade_context.get("realized_pnl_pct"), ratio=True)
        reason = str(trade_context.get("reason") or "未提供")
        market_snapshot = trade_context.get("market_snapshot") if isinstance(trade_context, dict) else None
        quote = market_snapshot.get("quote", {}) if isinstance(market_snapshot, dict) else {}
        industry = market_snapshot.get("industry", {}) if isinstance(market_snapshot, dict) else {}
        sentiment = market_snapshot.get("market_sentiment", {}) if isinstance(market_snapshot, dict) else {}
        main_inflow_yi = _fmt_yi(quote.get("main_net_inflow"))
        industry_name = str(industry.get("name") or quote.get("industry") or "未知行业")
        trade_result = (
            f"交易结果：已实现盈亏 {realized_pnl} 元，收益率 {realized_pnl_pct}。"
            if side == "sell"
            else "交易结果：买入成交，等待后续验证。"
        )
        return (
            "## 交易复盘\n\n"
            "| 股票名称 | 股票代码 | 买入价格 | 卖出价格 |\n"
            "| --- | --- | --- | --- |\n"
            f"| {name} | {symbol} | {cost_price} 元 | {price} 元 |\n\n"
            f"{trade_result}\n\n"
            f"操作原因：{reason}\n\n"
            "## 执行反思\n\n"
            f"{researcher_name} 需要重点复核成交纪律、仓位暴露与盘口承接。"
            f"成交时 {industry_name} 板块涨幅 {_fmt_pct(industry.get('change_pct'))}，"
            f"主力净流入 {main_inflow_yi}，涨停家数 {sentiment.get('limit_up_count', 0)} 家，"
            f"跌停家数 {sentiment.get('limit_down_count', 0)} 家。\n\n"
            "## 次日展望\n\n"
            f"- 若 {industry_name} 继续领涨且个股不破成交价，保留观察。\n"
            "- 若板块转弱或封单质量下降，优先降低仓位。\n"
        )

    async def build_trade_reflection(
        self,
        *,
        researcher_name: str,
        researcher_prompt: str,
        trade_context: dict[str, Any],
        allow_fallback: bool = True,
    ) -> str:
        """生成单笔成交复盘 markdown。

        流程:
          1) 拉取上下文(当日其他成交、这只票历史成交)
          2) 装配 prompt(教练口吻 + opinionated)
          3) 调 LLM(data profile,非流式;executor 是后台触发不需要 SSE)
          4) 失败时返回最小化确认信息,**不再生成套话模板**
        """
        llm = get_llm_client()
        if not llm.is_configured:
            if not allow_fallback:
                raise RuntimeError("LLM 服务未配置")
            return self._minimal_confirmation(trade_context)

        # 1. 上下文
        session = trade_context.get("session") if isinstance(trade_context, dict) else None
        account_id = trade_context.get("account_id") if isinstance(trade_context, dict) else None
        same_day_trades: list[TradeRecord] = []
        symbol_history: list[TradeRecord] = []
        if isinstance(session, AsyncSession) and account_id:
            symbol = str(trade_context.get("symbol") or "")
            same_day_trades, symbol_history = await self._load_context(
                session, account_id=account_id, symbol=symbol,
            )

        # 2. 构造 prompt
        system_prompt = self._build_system_prompt(researcher_name, researcher_prompt)
        user_msg = self._build_user_message(
            trade_context=trade_context,
            same_day_trades=same_day_trades,
            symbol_history=symbol_history,
        )

        # 3. LLM 调用(data profile 用便宜模型已经足够个体交易点评)
        try:
            reply = await llm.chat(
                [
                    LLMMessage("system", system_prompt),
                    LLMMessage("user", user_msg),
                ],
                profile="data",
                temperature=0.6,
                max_tokens=2500,
            )
        except Exception as exc:
            if not allow_fallback:
                raise
            logger.warning("交易复盘 LLM 失败: %s", exc)
            return self._minimal_confirmation(trade_context)

        text = reply.strip()
        if len(text) < 50:
            # LLM 给的内容太短,不像真正复盘
            return self._minimal_confirmation(trade_context)
        return text

    # ── 上下文加载 ──
    @staticmethod
    async def _load_context(
        session: AsyncSession, *, account_id: str, symbol: str,
    ) -> tuple[list[TradeRecord], list[TradeRecord]]:
        """加载当日其他成交 + 该股近 30 天成交。

        失败不抛,返回空列表。
        """
        try:
            today = datetime.utcnow().date()
            day_start = datetime.combine(today, time.min)
            day_end = datetime.combine(today, time.max)
            same_day_q = await session.execute(
                select(TradeRecord)
                .where(
                    TradeRecord.account_id == account_id,
                    TradeRecord.created_at >= day_start,
                    TradeRecord.created_at <= day_end,
                )
                .order_by(TradeRecord.created_at)
            )
            same_day = list(same_day_q.scalars().all())

            symbol_history: list[TradeRecord] = []
            if symbol:
                cutoff = datetime.combine(today - timedelta(days=30), time.min)
                hist_q = await session.execute(
                    select(TradeRecord)
                    .where(
                        TradeRecord.account_id == account_id,
                        TradeRecord.symbol == symbol,
                        TradeRecord.created_at >= cutoff,
                    )
                    .order_by(TradeRecord.created_at.desc())
                    .limit(10)
                )
                symbol_history = list(hist_q.scalars().all())
            return same_day, symbol_history
        except Exception:
            logger.exception("加载交易上下文失败")
            return [], []

    # ── prompt 装配 ──
    @staticmethod
    def _build_system_prompt(researcher_name: str, researcher_prompt: str) -> str:
        style = (researcher_prompt or "").strip()
        style_hint = f"研究员特征:{style}" if style else "研究员未配置专属风格,按通用短线纪律评估。"
        return (
            f"你是 {researcher_name} 的交易教练。每发生一笔成交,你必须写一份"
            "**针对这笔成交本身的评估**——不是描述成交,是评估对错。\n\n"
            f"{style_hint}\n\n"
            "核心纪律(违反一条整段判废):\n"
            "  1) 数字必须真实来自给你的数据,不许编。但鼓励基于真实数据做合理推断,"
            "不要用『本次未返回』这种套话遮掩——没数据时直接跳过该维度,不要硬填。\n"
            "  2) 必须有立场:这笔做得对不对,理由是什么。即使是盈利的卖出,也要找问题。\n"
            "  3) 禁止输出『继续保持』『加强学习』『控制风险』『仅供参考』这类废话。\n"
            "  4) 改进建议必须精确到行为(例如『下次若分时图破 5 日线即止损』),"
            "不要『加强纪律』这种空话。\n\n"
            "结构(灵活,按内容自然展开,**不要强求固定章节数**):\n"
            "## 一句话定性\n"
            "  X 分(1-10) — 这笔做得[漂亮 / 合格 / 勉强 / 糟糕],一句话说原因。\n\n"
            "## 这笔的核心问题\n"
            "  挑出 1-3 个最值得讨论的点(对的地方和错的地方都要)。\n"
            "  每个点必须基于具体数字 / 行情快照中的事实。\n\n"
            "## 放在当日组合里看\n"
            "  如果给了当日其他成交:讨论这笔与其他票的配合(分散 / 集中 / 互相抵消)。\n"
            "  如果没给:这一段简短说『今日单笔,不评估组合层面』即可。\n\n"
            "## 这只票的历史\n"
            "  如果给了历史成交:讨论这次相对历史的改进 / 退步。\n"
            "  如果没给:跳过此段。\n\n"
            "## 明天怎么办\n"
            "  必须给 **if-then 形式** 的具体动作(2-3 条),不允许空话。\n"
            "  例如:『若明日 09:30 该股开盘价 < 今日成本价 X 元,卖出 1/2 仓位;"
            "若开盘 +3% 且板块跟涨,继续持有,加止盈线到 +5%』。\n\n"
            "整体长度 600-1200 字,严禁灌水。Markdown 格式。"
        )

    @staticmethod
    def _build_user_message(
        *,
        trade_context: dict[str, Any],
        same_day_trades: list[TradeRecord],
        symbol_history: list[TradeRecord],
    ) -> str:
        """把所有信息装成一段给 LLM 的 user message。"""
        side = str(trade_context.get("side") or "buy")
        name = trade_context.get("name") or trade_context.get("symbol") or "-"
        symbol = trade_context.get("symbol") or "-"
        price = trade_context.get("price")
        quantity = trade_context.get("quantity")
        amount = trade_context.get("amount")
        commission = trade_context.get("commission")
        reason = trade_context.get("reason") or "(未提供)"
        cost_price = trade_context.get("cost_price")
        realized_pnl = trade_context.get("realized_pnl")
        realized_pnl_pct = trade_context.get("realized_pnl_pct")
        position_ratio = trade_context.get("position_ratio")
        total_asset = trade_context.get("total_asset")
        available_cash = trade_context.get("available_cash")
        market_snapshot = trade_context.get("market_snapshot")

        # 本笔成交
        lines = [
            "=== 本笔成交 ===",
            f"  方向:{'买入' if side == 'buy' else '卖出'}",
            f"  标的:{name}({symbol})",
            f"  成交价:{price}  数量:{quantity}  金额:{amount}  手续费:{commission}",
            f"  策略原因:{reason}",
        ]
        if side == "sell":
            lines.extend([
                f"  成本价:{cost_price}",
                f"  已实现盈亏:{realized_pnl}  盈亏比例:{realized_pnl_pct}",
            ])
        if position_ratio is not None:
            lines.append(f"  本笔仓位比:{position_ratio}")
        if total_asset is not None:
            lines.append(f"  账户总资产:{total_asset}  可用现金:{available_cash}")

        # market snapshot
        if isinstance(market_snapshot, dict):
            lines.append("\n=== 成交时行情快照 ===")
            for key in ("quote", "industry", "market_sentiment", "limit_up", "limit_down"):
                v = market_snapshot.get(key)
                if v:
                    lines.append(f"  {key}: {v}")
        else:
            lines.append("\n=== 成交时行情快照 ===\n  (未提供)")

        # 当日其他成交
        if same_day_trades:
            other = [t for t in same_day_trades if t.symbol != symbol]
            lines.append("\n=== 当日同账户其他成交(组合视角)===")
            if other:
                for t in other[-10:]:
                    lines.append(
                        f"  {t.created_at.strftime('%H:%M:%S')} "
                        f"{t.side} {t.name}({t.symbol}) "
                        f"{t.quantity}@{t.price:.2f} "
                        f"金额{t.quantity * t.price:.0f}"
                    )
            else:
                lines.append("  本笔是今天第一笔,无组合上下文。")

        # 该股历史
        if symbol_history:
            past = [t for t in symbol_history if not _is_same_trade(t, trade_context)]
            if past:
                lines.append(f"\n=== 该股({symbol})过去 30 天成交历史 ===")
                for t in past[:10]:
                    lines.append(
                        f"  {t.created_at.strftime('%Y-%m-%d %H:%M')} "
                        f"{t.side} {t.quantity}@{t.price:.2f}"
                    )

        return "\n".join(lines)

    # ── 失败兜底 ──
    @staticmethod
    def _minimal_confirmation(trade_context: dict[str, Any]) -> str:
        """LLM 不可用时的最小化确认信息。

        故意写得很短,不掩饰"AI 分析未生成"。
        宁可显示『复盘暂不可用』,也不要塞 200 行套话假装很有内容。
        """
        side = "买入" if trade_context.get("side") == "buy" else "卖出"
        name = trade_context.get("name") or trade_context.get("symbol") or "标的"
        symbol = trade_context.get("symbol") or "-"
        price = trade_context.get("price")
        quantity = trade_context.get("quantity")
        amount = trade_context.get("amount")
        return (
            f"## 成交确认\n\n"
            f"{side} **{name}({symbol})**,数量 {quantity},成交价 {price},金额 {amount}。\n\n"
            f"> AI 复盘暂不可用(LLM 服务异常或未配置)。"
            f"系统已记录本次成交,可前往交易记录查看明细。\n"
        )


def _is_same_trade(record: TradeRecord, ctx: dict[str, Any]) -> bool:
    """判断 record 是不是本笔成交(避免历史列表里把自己也算进去)。"""
    try:
        return (
            record.side == ctx.get("side")
            and float(record.price) == float(ctx.get("price") or 0)
            and record.quantity == int(ctx.get("quantity") or 0)
        )
    except (TypeError, ValueError):
        return False


def _fmt_money(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


def _fmt_pct(value: Any, *, ratio: bool = False) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "-"
    if ratio:
        number *= 100
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


def _fmt_yi(value: Any) -> str:
    try:
        number = float(value) / 100_000_000
    except (TypeError, ValueError):
        return "-"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f} 亿"
