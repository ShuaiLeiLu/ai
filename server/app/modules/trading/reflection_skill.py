"""交易反思 skill。

在每次模拟盘成交后输出一段结构化复盘，包含：
  - 交易动作与原因回放
  - 风险/执行反思
  - 次日观察与展望
"""
from __future__ import annotations

import logging
from typing import Any

from app.integrations.llm.client import LLMMessage, get_llm_client

logger = logging.getLogger(__name__)


class TradingReflectionSkill:
    """统一生成交易复盘内容，优先走 LLM，失败时回退模板。"""

    def build_trade_log_title(self, trade_context: dict[str, Any]) -> str:
        action = "买入操作播报" if trade_context.get("side") == "buy" else "卖出操作播报"
        name = str(trade_context.get("name") or trade_context.get("symbol") or "交易")
        symbol = str(trade_context.get("symbol") or "").strip()
        return f"{action}｜{name}({symbol})" if symbol else f"{action}｜{name}"

    @staticmethod
    def _as_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _money(value: Any) -> str:
        return f"{TradingReflectionSkill._as_float(value):,.2f} 元"

    @staticmethod
    def _price(value: Any) -> str:
        return f"{TradingReflectionSkill._as_float(value):.2f} 元"

    @staticmethod
    def _pct(value: Any) -> str:
        if value is None:
            return "-"
        return f"{TradingReflectionSkill._as_float(value) * 100:+.2f}%"

    @staticmethod
    def _position_pct(value: Any) -> str:
        ratio = TradingReflectionSkill._as_float(value)
        return f"{ratio * 100:.2f}%" if ratio > 0 else "-"

    @staticmethod
    def _amount_yi(value: Any) -> str:
        return f"{TradingReflectionSkill._as_float(value) / 100000000:.2f} 亿"

    @staticmethod
    def _flow_yi(value: Any) -> str:
        val = TradingReflectionSkill._as_float(value) / 100000000
        return f"{val:+.2f} 亿"

    @staticmethod
    def _raw_pct(value: Any) -> str:
        return f"{TradingReflectionSkill._as_float(value):+.2f}%"

    @staticmethod
    def _dict_value(mapping: Any, key: str, default: Any = None) -> Any:
        return mapping.get(key, default) if isinstance(mapping, dict) else default

    def _build_market_snapshot_lines(self, trade_context: dict[str, Any]) -> list[str]:
        snapshot = trade_context.get("market_snapshot")
        if not isinstance(snapshot, dict):
            return ["本次成交未能获取行情快照，复盘仅使用真实成交和账户数据。"]

        quote = self._dict_value(snapshot, "quote")
        industry = self._dict_value(snapshot, "industry")
        sentiment = self._dict_value(snapshot, "market_sentiment") or {}
        limit_up = self._dict_value(snapshot, "limit_up")
        limit_down = self._dict_value(snapshot, "limit_down")
        snapshot_at = str(snapshot.get("snapshot_at") or self._dict_value(sentiment, "snapshot_at") or "-")

        lines = [f"行情快照时间：{snapshot_at}"]

        if isinstance(quote, dict):
            lines.extend(
                [
                    "",
                    "| 指标 | 数值 |",
                    "| --- | ---: |",
                    f"| 最新价 | {self._price(self._dict_value(quote, 'price'))} |",
                    f"| 涨跌幅 | {self._raw_pct(self._dict_value(quote, 'change_pct'))} |",
                    f"| 今开/最高/最低 | {self._price(self._dict_value(quote, 'open'))} / {self._price(self._dict_value(quote, 'high'))} / {self._price(self._dict_value(quote, 'low'))} |",
                    f"| 成交额 | {self._amount_yi(self._dict_value(quote, 'amount'))} |",
                    f"| 换手率 | {self._raw_pct(self._dict_value(quote, 'turnover_ratio'))} |",
                    f"| 量比 | {self._as_float(self._dict_value(quote, 'volume_ratio')):.2f} |",
                    f"| 主力净流入 | {self._flow_yi(self._dict_value(quote, 'main_net_inflow'))} |",
                    f"| 主力净占比 | {self._raw_pct(self._dict_value(quote, 'main_net_inflow_pct'))} |",
                    f"| 所属行业 | {self._dict_value(quote, 'industry', '-') or '-'} |",
                ]
            )
        else:
            lines.append("个股实时行情未获取成功。")

        if isinstance(industry, dict):
            lines.extend(
                [
                    "",
                    "| 板块指标 | 数值 |",
                    "| --- | ---: |",
                    f"| 板块名称 | {self._dict_value(industry, 'name', '-') or '-'} |",
                    f"| 板块涨跌幅 | {self._raw_pct(self._dict_value(industry, 'change_pct'))} |",
                    f"| 板块成交额 | {self._as_float(self._dict_value(industry, 'total_amount')):.2f} 亿 |",
                    f"| 板块净流入 | {self._flow_yi(self._as_float(self._dict_value(industry, 'net_inflow')) * 100000000)} |",
                    f"| 上涨/下跌家数 | {int(self._as_float(self._dict_value(industry, 'rise_count')))} / {int(self._as_float(self._dict_value(industry, 'fall_count')))} |",
                    f"| 领涨股 | {self._dict_value(industry, 'leading_stock', '-') or '-'} {self._raw_pct(self._dict_value(industry, 'leading_stock_pct'))} |",
                ]
            )

        if isinstance(sentiment, dict):
            top_industries = self._dict_value(sentiment, "top_limit_industries", [])
            top_text = "、".join(
                f"{item.get('industry')}({item.get('limit_up_count')}家)"
                for item in top_industries
                if isinstance(item, dict) and item.get("industry")
            ) or "-"
            lines.extend(
                [
                    "",
                    "| 情绪指标 | 数值 |",
                    "| --- | ---: |",
                    f"| 涨停家数 | {int(self._as_float(self._dict_value(sentiment, 'limit_up_count')))} 家 |",
                    f"| 跌停家数 | {int(self._as_float(self._dict_value(sentiment, 'limit_down_count')))} 家 |",
                    f"| 连板家数 | {int(self._as_float(self._dict_value(sentiment, 'multi_board_count')))} 家 |",
                    f"| 最高连板 | {int(self._as_float(self._dict_value(sentiment, 'highest_consecutive')))} 板 |",
                    f"| 涨停集中方向 | {top_text} |",
                ]
            )

        if isinstance(limit_up, dict):
            lines.append(
                f"\n涨停池状态：{limit_up.get('name')}({limit_up.get('symbol')}) 位于涨停池，"
                f"{int(self._as_float(limit_up.get('consecutive')))} 连板，炸板 {int(self._as_float(limit_up.get('break_count')))} 次。"
            )
        elif isinstance(limit_down, dict):
            lines.append(
                f"\n跌停池状态：{limit_down.get('name')}({limit_down.get('symbol')}) 位于跌停池，"
                f"跌幅 {self._raw_pct(limit_down.get('change_pct'))}。"
            )
        else:
            lines.append("\n涨跌停池状态：本标的未出现在当前涨停池/跌停池。")

        return lines

    def build_fallback_reflection(
        self,
        *,
        researcher_name: str,
        researcher_prompt: str,
        trade_context: dict[str, Any],
    ) -> str:
        side = str(trade_context.get("side") or "buy")
        action_label = "买入" if side == "buy" else "卖出"
        symbol = str(trade_context.get("symbol") or "-")
        name = str(trade_context.get("name") or symbol)
        quantity = int(trade_context.get("quantity") or 0)
        price = self._as_float(trade_context.get("price"))
        amount = self._as_float(trade_context.get("amount"))
        commission = self._as_float(trade_context.get("commission"))
        reason = str(trade_context.get("reason") or "按既定交易计划执行")
        realized_pnl = trade_context.get("realized_pnl")
        realized_pnl_pct = trade_context.get("realized_pnl_pct")
        total_asset = self._as_float(trade_context.get("total_asset"))
        available_cash = self._as_float(trade_context.get("available_cash"))
        cost_price = trade_context.get("cost_price")
        position_ratio = self._as_float(trade_context.get("position_ratio"))
        style_hint = researcher_prompt.strip() or "围绕小市值轮动纪律做交易复盘"
        market_lines = self._build_market_snapshot_lines(trade_context)

        if side == "buy":
            trade_table = [
                "| 股票名称 | 股票代码 | 买入价格 | 买入数量 | 买入金额 | 仓位比例 |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
                f"| {name} | {symbol} | {self._price(price)} | {quantity} 股 | {self._money(amount)} | {self._position_pct(position_ratio)} |",
            ]
            broadcast = (
                f"刚按计划买入 {name}({symbol}) {quantity} 股，成交价 {price:.2f} 元，"
                f"成交额 {amount:,.2f} 元。"
            )
            operation_logic = (
                f"这笔开仓来自当前策略信号：{reason}。盘面判断以成交时采集到的行情快照为准，"
                "若快照字段缺失则只对缺失字段保持空白，不补写假数据。"
            )
            execution_check = (
                f"执行层面已经完成建仓，手续费 {commission:,.2f} 元，仓位约 {position_ratio * 100:.2f}%。"
                "后续重点不是主观加戏，而是观察成交后的承接、板块联动和仓位暴露是否仍符合研究员规则。"
            )
            outlook = (
                f"下一交易日优先看 {name}({symbol}) 开盘强弱、价格是否守住本次成交成本附近，"
                "以及同题材是否继续有资金响应。若开盘明显不及预期，先执行止损/减仓纪律；"
                "若承接继续增强，再评估是否继续持有，不因为一笔买入就和标的绑定。"
            )
        else:
            pnl_value = self._as_float(realized_pnl)
            result = "盈利" if pnl_value > 0 else "亏损" if pnl_value < 0 else "持平"
            buy_price = cost_price if cost_price is not None else "-"
            trade_table = [
                "| 股票名称 | 股票代码 | 买入价格 | 卖出价格 | 卖出数量 | 卖出金额 | 盈亏金额 | 盈亏比例 | 交易结果 |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
                (
                    f"| {name} | {symbol} | {self._price(buy_price) if buy_price != '-' else '-'} | "
                    f"{self._price(price)} | {quantity} 股 | {self._money(amount)} | "
                    f"{pnl_value:+,.2f} 元 | {self._pct(realized_pnl_pct)} | {result} |"
                ),
            ]
            broadcast = (
                f"刚卖出 {name}({symbol}) {quantity} 股，成交价 {price:.2f} 元，"
                f"本次平仓 {pnl_value:+,.2f} 元，结果为{result}。"
            )
            operation_logic = (
                f"退出触发来自当前策略信号：{reason}。卖出判断结合真实成交、成本、盈亏和行情快照；"
                "接口未返回的字段不做主观补全。"
            )
            execution_check = (
                f"这次卖出回收资金 {amount:,.2f} 元，手续费 {commission:,.2f} 元。"
                "卖出后的核心是复核退出是否提升组合效率：盈利时防止利润回吐，亏损时确认是否及时截断风险。"
            )
            outlook = (
                f"下一交易日继续跟踪 {name}({symbol}) 卖出后的反馈，验证本次退出是否有效。"
                "若原标的反包但没有新的买入信号，不追悔；若板块继续走强，优先寻找有真实成交计划支持的替代机会。"
            )

        account_lines = []
        if total_asset > 0 or available_cash > 0:
            account_lines = [
                "| 指标 | 数值 |",
                "| --- | ---: |",
                f"| 当前总资产 | {self._money(total_asset)} |",
                f"| 当前可用资金 | {self._money(available_cash)} |",
            ]

        lines = [
            "## 交易复盘",
            "### 操作播报",
            broadcast,
            "",
            *trade_table,
            "",
            "### 盘面数据",
            *market_lines,
            "",
            "### 操作逻辑",
            operation_logic,
            "",
            "### 研究员设定",
            f"{researcher_name}：{style_hint}",
            "",
            "## 执行反思",
            "### 纪律检查",
            execution_check,
            "",
            "### 风险控制",
            "这条日志的重点是把真实成交复盘成可复核的动作链：为什么动、动了多少、盘面当时给了什么反馈、结果如何、下一步怎么处理。行情字段来自成交时快照，避免用静态文案遮掩真实风险。",
        ]
        if account_lines:
            lines.extend(["", "### 账户状态", *account_lines])
        lines.extend(["", "## 次日展望", "### 观察重点", outlook, "", "### 交易预案"])
        if side == "buy":
            lines.append(
                "若次日承接强于预期，优先持有观察；若跌破成本区且板块没有共振，按规则减仓或止损，避免把短线交易拖成长线被动持仓。"
            )
        else:
            lines.append(
                "卖出后资金先保持机动，等待新的真实信号和成交条件出现；不因为刚卖出就立刻寻找补偿性交易。"
            )

        return "\n".join(lines)

    async def build_trade_reflection(
        self,
        *,
        researcher_name: str,
        researcher_prompt: str,
        trade_context: dict[str, Any],
        allow_fallback: bool = True,
    ) -> str:
        llm = get_llm_client()
        fallback = self.build_fallback_reflection(
            researcher_name=researcher_name,
            researcher_prompt=researcher_prompt,
            trade_context=trade_context,
        )
        if not llm.is_configured:
            if not allow_fallback:
                raise RuntimeError("LLM 服务未配置")
            return fallback

        system_prompt = (
            "你是一名A股超短交易复盘研究员。你要学习用户给出的工作日志形式："
            "按成交事实先做 TRADE 式表格，再写操作播报、盘面数据、操作逻辑、执行反思和次日预案。"
            "请严格使用 Markdown，并且只使用这三个二级标题作为大段："
            "`## 交易复盘`、`## 执行反思`、`## 次日展望`。"
            "每个大段下面可以使用 `### 操作播报`、`### 盘面数据`、`### 操作逻辑`、`### 纪律检查`、`### 观察重点` 等三级标题。"
            "交易表格必须根据 side 输出：买入表包含股票名称、股票代码、买入价格、买入数量、买入金额、仓位比例；"
            "卖出表包含股票名称、股票代码、买入价格、卖出价格、卖出数量、卖出金额、盈亏金额、盈亏比例、交易结果。"
            "只能引用交易上下文里真实存在的价格、数量、金额、盈亏、账户字段和 market_snapshot；"
            "盘口强弱、主力资金、涨停数量、板块涨跌、成交额等必须优先从 market_snapshot 读取。"
            "market_snapshot 没有提供的字段，必须明确写“本次快照未返回”，禁止编造具体数字。"
            "文风可以有临盘复盘的力度，但要专业克制，不喊单、不承诺收益、不写投资建议。"
        )
        user_prompt = (
            f"研究员名称：{researcher_name}\n"
            f"研究员提示词：{researcher_prompt or '未额外配置'}\n"
            f"交易上下文：{trade_context}\n\n"
            "请围绕这次成交生成一条完整的 AI 交易复盘工作流日志。"
            "结构要像真实交易日志：先有成交表，再有操作播报/盘面数据/操作逻辑，随后执行反思和次日展望。"
        )

        try:
            reply = await llm.chat(
                [
                    LLMMessage(role="system", content=system_prompt),
                    LLMMessage(role="user", content=user_prompt),
                ],
                temperature=0.4,
                max_tokens=900,
            )
            text = reply.strip()
            required_sections = ("## 交易复盘", "## 执行反思", "## 次日展望")
            if not all(section in text for section in required_sections):
                if not allow_fallback:
                    raise RuntimeError("LLM 复盘缺少必要章节")
                return fallback
            return text
        except Exception as exc:
            if not allow_fallback:
                raise
            logger.warning("交易复盘 LLM 生成失败，回退模板: %s", exc)
            return fallback
