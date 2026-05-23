"""LimitUpStructureSkill —— 涨停结构 + 接力推演。

为什么不是简单统计涨停个数:
  关键在判断"今天市场处于接力 / 高低切 / 退潮"三选一的情绪周期位置,
  这是 A 股短线市场的核心判断。

输入:
  - 涨停池 / 跌停池 / 强势股池(同日)
输出:
  narrative: 300-500 字判断
  structured: {
    "cycle_phase": "relay" | "rotation" | "decay",
    "leader_consecutive": int,
    "leader_symbols": [...],
    "limit_up_count": int,
    "limit_down_count": int,
    "seal_ratio": float,
    "key_signals": [...]
  }
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.integrations.akshare.client import (
    get_limit_down_pool,
    get_limit_up_pool,
    get_strong_pool,
)
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.skills.base import SkillBase, SkillContext, SkillResult
from app.skills.shared.data_loaders import load
from app.skills.shared.parsers import split_narrative_and_json
from app.skills.shared.prompts import A_SHARE_CONTEXT, DATA_SKILL_GUARDRAILS


class LimitUpStructureSkill(SkillBase):
    name = "limit_up_structure"
    description = "涨停结构 + 接力推演,判断情绪周期处于接力/高低切/退潮哪一阶段"
    depends_on: list[str] = []
    model_profile = "data"

    async def _execute(self, ctx: SkillContext) -> SkillResult:
        pool = await load(get_limit_up_pool)
        dt_pool = await load(get_limit_down_pool)
        strong = await load(get_strong_pool)

        data_text = self._format_data(pool, dt_pool, strong)
        if not pool and not strong:
            return SkillResult(
                skill_name=self.name,
                success=True,
                narrative="今日涨停池/强势股池为空,无法判断市场情绪结构。",
                structured={
                    "cycle_phase": "unknown",
                    "limit_up_count": 0,
                    "limit_down_count": len(dt_pool or []),
                    "key_signals": ["数据缺失"],
                },
            )

        system = (
            "你是 A 股短线游资派分析师,擅长判断市场情绪周期位置。\n\n"
            f"{A_SHARE_CONTEXT}\n"
            f"{DATA_SKILL_GUARDRAILS}\n"
            "\n本次任务:基于涨停池/跌停池/强势股池数据,判断今日(或最近一个交易日)\n"
            "情绪周期处于以下哪个阶段,并给出 300-500 字的判断理由:\n"
            "  - relay:接力(高度板顺利,资金有合力,炸板率低)\n"
            "  - rotation:高低切(高度板炸板/分歧,资金切到补涨/低位)\n"
            "  - decay:退潮(涨停大幅萎缩、连板断层、跌停增多)\n"
            "\n输出格式:\n"
            "  [一段 300-500 字的判断,引用具体数字]\n"
            "  ```json\n"
            "  {\n"
            '    "cycle_phase": "relay|rotation|decay",\n'
            '    "leader_consecutive": <最高连板数>,\n'
            '    "leader_symbols": ["XX(代码)", "YY(代码)"],\n'
            '    "limit_up_count": <涨停家数>,\n'
            '    "limit_down_count": <跌停家数>,\n'
            '    "seal_ratio": <封板率%>,\n'
            '    "key_signals": ["关键信号1", "关键信号2"]\n'
            "  }\n"
            "  ```"
        )

        try:
            reply = await get_llm_client().chat(
                [
                    LLMMessage("system", system),
                    LLMMessage("user", data_text),
                ],
                profile=self.model_profile,
                max_tokens=1200,
            )
        except Exception as exc:
            return SkillResult(
                skill_name=self.name,
                success=False,
                error=f"LLM 调用失败: {exc}",
            )

        narrative, structured = split_narrative_and_json(reply)
        # 数据兜底:即使 LLM 没给 structured,也把基础统计塞进去
        structured.setdefault("limit_up_count", len(pool))
        structured.setdefault("limit_down_count", len(dt_pool))
        structured.setdefault(
            "leader_consecutive",
            max((s.consecutive for s in pool), default=0),
        )

        return SkillResult(
            skill_name=self.name,
            success=True,
            narrative=narrative or reply,
            structured=structured,
        )

    @staticmethod
    def _format_data(pool: list, dt_pool: list, strong: list) -> str:
        total_zt = len(pool)
        total_dt = len(dt_pool)
        max_consecutive = max((s.consecutive for s in pool), default=0)
        multi_board = sum(1 for s in pool if s.consecutive >= 2)
        no_break = sum(
            1 for s in pool if int(getattr(s, "break_count", 0) or 0) == 0
        )
        seal_ratio = round(no_break / total_zt * 100, 1) if total_zt else 0.0

        industry_counter: Counter[str] = Counter(
            s.industry for s in pool if s.industry
        )
        top_industries = industry_counter.most_common(5)

        sorted_pool = sorted(
            pool, key=lambda s: (s.consecutive, s.amount), reverse=True
        )
        leaders = "\n".join(
            f"  - {s.name}({s.symbol}) {s.consecutive}连板 "
            f"行业:{s.industry} 炸板:{getattr(s, 'break_count', 0)} 次 "
            f"换手:{s.turnover_ratio:.1f}%"
            for s in sorted_pool[:12]
        ) or "  (无涨停)"

        bottom_pool = sorted(pool, key=lambda s: s.consecutive)[:5]
        bottom_text = "\n".join(
            f"  - {s.name}({s.symbol}) 1板 "
            f"换手:{s.turnover_ratio:.1f}%"
            for s in bottom_pool
        )

        return (
            f"=== 涨停池结构(共 {total_zt} 家)===\n"
            f"  最高连板:{max_consecutive} 板\n"
            f"  连板家数(≥2):{multi_board}\n"
            f"  未炸板:{no_break} 家,封板率:{seal_ratio}%\n\n"
            f"=== 跌停池(共 {total_dt} 家)===\n"
            f"  对比涨停:涨停/跌停 = {total_zt}/{total_dt}\n\n"
            f"=== 强势股池(共 {len(strong)} 家)===\n"
            f"  涨幅 5-10% 的活跃股\n\n"
            f"=== 涨停行业分布(前 5)===\n"
            + "\n".join(f"  - {ind}: {cnt} 家" for ind, cnt in top_industries)
            + f"\n\n=== 龙头梯队(按连板+成交额)===\n{leaders}\n\n"
            f"=== 一板(基础位)===\n{bottom_text}"
        )
