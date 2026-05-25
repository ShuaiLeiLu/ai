"""
盘前速览聚合服务 —— 真实数据版

数据来源：
  - 热讯榜：AKShare stock_news_main_cx（财新头条）
  - 市场指标：AKShare stock_zt_pool_em（涨停池统计：涨停家数、最高连板、封板率等）
  - 涨停天梯：AKShare stock_zt_pool_em（按连板数排序）
  - 异常波动：AKShare stock_zt_pool_strong_em + stock_zt_pool_dtgc_em（强势股+跌停股中筛选）
  - AI 解读：基于涨停池数据聚合生成
  - 趋势数据：每日盘前市场快照落库后，基于真实历史快照生成

所有 AKShare 调用在 client 层带 TTL 缓存。
"""
from __future__ import annotations

import hashlib
import logging
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.client import (
    get_industry_boards,
    get_limit_down_pool,
    get_limit_up_pool,
    get_live_news_merged,
    get_strong_pool,
    run_sync,
)
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.preopen import PreopenAiDigest, PreopenMarketSnapshot
from app.modules.preopen.schemas import (
    AiDigest,
    AiDigestSection,
    AnomalyItem,
    AnomalyOverview,
    HotNewsItem,
    IndustryBoardItem,
    LimitUpLadderItem,
    MarketIndicator,
    StockRankItem,
    TradingCalendarHint,
    TrendOverview,
    TrendPoint,
    TrendSeries,
)

logger = logging.getLogger(__name__)

# LLM 结果缓存（5 分钟）
_llm_digest_cache: dict[str, Any] = {"data": None, "expires_at": 0.0}
_LLM_CACHE_TTL = 300  # 5 分钟


def ai_digest_from_persisted(row: PreopenAiDigest) -> AiDigest:
    """Convert the daily persisted skill-chain digest into the public card schema."""
    main_struct = (
        row.skill_outputs.get("main_thesis", {}) if row.skill_outputs else {}
    ).get("structured", {})
    if not isinstance(main_struct, dict):
        main_struct = {}
    core_thesis = str(main_struct.get("core_thesis") or "").strip()
    headline = core_thesis or _first_markdown_text(row.main_thesis_md) or "盘前 AI 解读已生成"
    key_points = _markdown_bullets(row.main_thesis_md)
    if not key_points:
        key_points = [headline]
    sentiment = {
        "bullish": "bullish",
        "bearish": "bearish",
        "retreat": "bearish",
    }.get((row.bias or "").lower(), "neutral")
    return AiDigest(
        digest_id=row.id,
        report_title=_digest_report_title(row.trade_date),
        headline=headline,
        interval_start=row.generated_at,
        interval_end=row.generated_at,
        generated_at=row.generated_at,
        sentiment=sentiment,
        key_points=key_points[:5],
        report_sections=_sections_from_markdown(row.main_thesis_md),
        news_drivers=[],
        opportunity_sectors=[core_thesis] if core_thesis else [],
        risk_sectors=list(row.falsification_signals or []),
        intraday_watch=list(main_struct.get("intraday_checkpoints") or []),
        simulation_plan=list(main_struct.get("operation_discipline") or []),
    )


def _first_markdown_text(markdown: str) -> str:
    for raw in markdown.splitlines():
        line = raw.strip().lstrip("#").strip()
        if line and not line.startswith("```"):
            return line
    return ""


def _markdown_bullets(markdown: str) -> list[str]:
    bullets: list[str] = []
    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith(("- ", "* ")):
            item = line[2:].strip()
            if item:
                bullets.append(item)
    return bullets


def _sections_from_markdown(markdown: str) -> list[AiDigestSection]:
    sections: list[AiDigestSection] = []
    current_title = ""
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_title, current_lines
        if not current_title:
            return
        paragraphs = [line for line in current_lines if line and not line.startswith(("- ", "* "))]
        bullets = [line[2:].strip() for line in current_lines if line.startswith(("- ", "* "))]
        sections.append(AiDigestSection(title=current_title, paragraphs=paragraphs, bullets=bullets))
        current_lines = []

    for raw in markdown.splitlines():
        line = raw.strip()
        if line.startswith("## "):
            flush()
            current_title = line.lstrip("#").strip()
            current_lines = []
            continue
        if line:
            current_lines.append(line)
    flush()
    if sections:
        return sections
    return [AiDigestSection(title="盘前 AI 解读", paragraphs=[markdown.strip()])] if markdown.strip() else []


def _digest_report_title(calendar_trade_date: date) -> str:
    return f"研判官·{calendar_trade_date.strftime('%m月%d日')}盘前热讯全洞察报告"


def _build_digest_sections(
    *,
    headline: str,
    key_points: list[str],
    news_drivers: list[str],
    opportunity_sectors: list[str],
    risk_sectors: list[str],
    intraday_watch: list[str],
    simulation_plan: list[str],
    total_zt: int | None = None,
    multi_board: int | None = None,
    max_consecutive: int | None = None,
    industry_text: str | None = None,
) -> list[AiDigestSection]:
    overview_rows = [
        {"指标": "涨停家数", "当前值": str(total_zt if total_zt is not None else "待同步"), "观察": "情绪强度核心指标"},
        {"指标": "连板数量", "当前值": str(multi_board if multi_board is not None else "待同步"), "观察": "短线接力温度"},
        {"指标": "最高连板", "当前值": str(max_consecutive if max_consecutive is not None else "待同步"), "观察": "高度空间"},
        {"指标": "主线方向", "当前值": industry_text or "待同步", "观察": "资金攻击方向"},
    ]
    opportunity_text = "、".join(opportunity_sectors[:5]) or "暂无明确机会方向，等待开盘资金验证。"
    risk_text = "、".join(risk_sectors[:5]) or "暂无明显扩散风险，但仍需跟踪高位题材回落。"

    return [
        AiDigestSection(
            title="一、先抛观点：核心判断",
            paragraphs=[headline],
            bullets=key_points[:5],
        ),
        AiDigestSection(
            title="二、盘面速览：市场结构",
            paragraphs=["用涨跌停生态、连板高度和行业集中度判断开盘前情绪温度。"],
            table=overview_rows,
        ),
        AiDigestSection(
            title="三、快讯分类总表",
            paragraphs=["以下新闻驱动来自最新热讯与实时快讯，优先关注能形成板块映射的催化。"],
            bullets=news_drivers[:8] or ["暂无可用快讯，建议开盘后观察资金选择。"],
        ),
        AiDigestSection(
            title="四、矛盾点挖掘",
            paragraphs=[
                f"机会方向集中在 {opportunity_text}；风险方向集中在 {risk_text}。",
                "若新闻强、板块弱，说明资金认可度不足；若板块先行扩散，则题材有望从消息驱动切换为资金驱动。",
            ],
        ),
        AiDigestSection(
            title="五、资金与情绪信号",
            bullets=intraday_watch[:6] or ["观察开盘 15 分钟成交额承接。", "观察昨日涨停溢价和连板晋级率。"],
        ),
        AiDigestSection(
            title="六、核心题材深挖",
            paragraphs=[f"重点跟踪：{opportunity_text}。"],
            bullets=[f"{sector}：等待竞价强度、涨停扩散和龙头封单共同确认。" for sector in opportunity_sectors[:5]],
        ),
        AiDigestSection(
            title="七、风险警示",
            bullets=risk_sectors[:6] or ["暂无明显扩散风险。"],
        ),
        AiDigestSection(
            title="八、操作铁律",
            bullets=[
                "不追无板块共振的单点消息。",
                "单一方向仓位不超过总仓位三成。",
                "若开盘半小时热点未扩散，降低追涨动作。",
                "若炸板率快速上升，优先保护模拟盘收益。",
            ],
        ),
        AiDigestSection(
            title="九、重点盯盘清单",
            bullets=simulation_plan[:6] or ["只在新闻、题材和资金三者共振时开仓。"],
        ),
        AiDigestSection(
            title="十、总结",
            paragraphs=["本报告用于盘前观察和模拟盘推演，不构成投资建议。开盘后以真实成交量、涨停扩散和风险事件变化为准。"],
        ),
    ]


def _make_calendar() -> TradingCalendarHint:
    """构建交易日历提示。"""
    today = date.today()
    is_trading = today.weekday() < 5
    trade_date = today
    if not is_trading:
        while trade_date.weekday() >= 5:
            trade_date -= timedelta(days=1)
    return TradingCalendarHint(
        trade_date=trade_date,
        is_trading_day=is_trading,
        notice="非交易日展示最近交易日快照" if not is_trading else "盘前快照数据",
    )


class PreopenService:
    """盘前速览聚合服务 —— 基于 AKShare 真实数据。

    所有方法同步执行，router 层通过 await run_sync(...) 调用。
    """

    # ─────────────── 热讯榜 ───────────────

    def list_hot_news(self) -> list[HotNewsItem]:
        """热讯榜 —— 同花顺 7x24 快讯 + 财联社快讯合并。

        数据质量：真实标题、正文、精确发布时间、原文链接。
        同花顺为主力数据源，财联社为补充，合并去重后按时间倒序。
        """
        live_news = get_live_news_merged()
        now = datetime.now(tz=UTC)

        items: list[HotNewsItem] = []
        for i, raw in enumerate(live_news[:15]):
            news_id = "hn_" + hashlib.md5(raw.title.encode()).hexdigest()[:8]

            # 解析真实发布时间
            try:
                published_at = datetime.fromisoformat(raw.publish_time.replace(" ", "T"))
                if published_at.tzinfo is None:
                    published_at = published_at.replace(tzinfo=UTC)
            except (ValueError, AttributeError):
                published_at = now - timedelta(minutes=i * 10)

            # 情绪判断：基于标题+内容关键词
            text = raw.title + raw.content
            if any(w in text for w in ("涨", "突破", "新高", "利好", "增长", "上调", "预增")):
                sentiment = "bullish"
            elif any(w in text for w in ("跌", "利空", "风险", "下降", "战争", "制裁", "封锁", "暴跌")):
                sentiment = "bearish"
            else:
                sentiment = "neutral"

            items.append(HotNewsItem(
                news_id=news_id,
                title=raw.title,
                summary=raw.content[:200] if raw.content else raw.title,
                source=raw.source,
                published_at=published_at,
                heat=max(100 - i * 5, 30),
                sentiment=sentiment,
                symbols=[],
                jump_type="news",
                jump_target=raw.url or "/news",
            ))
        return items

    # ─────────────── AI 解读 ───────────────

    def _collect_preopen_data_text(self) -> str:
        """收集盘前相关数据，拼装为文本供 LLM 分析。"""
        pool = get_limit_up_pool()
        strong = get_strong_pool()
        dt_pool = get_limit_down_pool()
        live_news = get_live_news_merged()

        total_zt = len(pool)
        total_dt = len(dt_pool)
        max_consecutive = max((s.consecutive for s in pool), default=0) if pool else 0
        multi_board = sum(1 for s in pool if s.consecutive >= 2)

        industry_counter = Counter(s.industry for s in pool if s.industry)
        top_industries = industry_counter.most_common(5)

        # 涨停个股明细（前 10 只）
        sorted_pool = sorted(pool, key=lambda s: (s.consecutive, s.amount), reverse=True)
        stock_details = "\n".join(
            f"  - {s.name}({s.symbol}) {s.consecutive}连板 行业:{s.industry}"
            for s in sorted_pool[:10]
        ) or "  暂无涨停数据"

        # 最新快讯（前 8 条）
        news_titles = "\n".join(
            f"  - [{n.source}] {n.title}" for n in live_news[:8]
        ) or "  暂无快讯"

        return (
            f"=== 盘前市场快照 ===\n"
            f"涨停: {total_zt} 家 | 跌停: {total_dt} 家 | 强势股: {len(strong)} 家\n"
            f"连板: {multi_board} 家（最高 {max_consecutive} 连板）\n\n"
            f"行业涨停分布:\n"
            + "\n".join(f"  - {ind}: {cnt}家" for ind, cnt in top_industries)
            + f"\n\n涨停龙头:\n{stock_details}"
            + f"\n\n最新快讯:\n{news_titles}"
        )

    def get_ai_digest(self) -> AiDigest:
        """AI 热讯解读模板 —— 基于涨停池数据自动生成摘要。"""
        now = datetime.now(tz=UTC)
        calendar = _make_calendar()
        pool = get_limit_up_pool()

        total_zt = len(pool)
        max_consecutive = max((s.consecutive for s in pool), default=0) if pool else 0
        multi_board = sum(1 for s in pool if s.consecutive >= 2)

        industry_counter = Counter(s.industry for s in pool if s.industry)
        top_industries = industry_counter.most_common(3)
        industry_text = "、".join(f"{ind}" for ind, _ in top_industries) if top_industries else "暂无行业数据"

        if total_zt > 60:
            sentiment = "bullish"
            mood = "偏多"
        elif total_zt < 30:
            sentiment = "bearish"
            mood = "偏空"
        else:
            sentiment = "neutral"
            mood = "中性"

        headline = f"盘前情绪{mood}，涨停 {total_zt} 家，资金主攻 {industry_text}"

        key_points = [
            f"涨停家数 {total_zt}，连板 {multi_board} 家，最高 {max_consecutive} 连板。",
            f"涨停行业集中于：{industry_text}。",
        ]

        strong = get_strong_pool()
        if strong:
            key_points.append(f"强势股池 {len(strong)} 家，{'市场整体偏强' if len(strong) > 150 else '市场强度温和'}。")

        return AiDigest(
            digest_id=f"digest_{calendar.trade_date.isoformat()}",
            report_title=_digest_report_title(calendar.trade_date),
            headline=headline,
            interval_start=now - timedelta(hours=12),
            interval_end=now,
            generated_at=now,
            sentiment=sentiment,
            key_points=key_points,
            report_sections=_build_digest_sections(
                headline=headline,
                key_points=key_points,
                news_drivers=[n.title for n in get_live_news_merged()[:8]],
                opportunity_sectors=[ind for ind, _ in top_industries[:3]],
                risk_sectors=["跌停池扩散方向" if len(get_limit_down_pool()) > 5 else "暂无明显扩散风险"],
                intraday_watch=[
                    "09:25-09:40 观察昨日涨停溢价和连板高度是否继续打开",
                    "10:30 前确认资金是否沿新闻催化方向形成板块共振",
                ],
                simulation_plan=[
                    "模拟盘只在新闻方向、涨停结构和个股承接共振时开仓",
                    "若热点只有单点消息无板块跟随，优先观望或降低仓位",
                ],
                total_zt=total_zt,
                multi_board=multi_board,
                max_consecutive=max_consecutive,
                industry_text=industry_text,
            ),
            news_drivers=[n.title for n in get_live_news_merged()[:3]],
            opportunity_sectors=[ind for ind, _ in top_industries[:3]],
            risk_sectors=["跌停池扩散方向" if len(get_limit_down_pool()) > 5 else "暂无明显扩散风险"],
            intraday_watch=[
                "09:25-09:40 观察昨日涨停溢价和连板高度是否继续打开",
                "10:30 前确认资金是否沿新闻催化方向形成板块共振",
            ],
            simulation_plan=[
                "模拟盘只在新闻方向、涨停结构和个股承接共振时开仓",
                "若热点只有单点消息无板块跟随，优先观望或降低仓位",
            ],
        )

    async def generate_ai_digest_with_llm(self) -> AiDigest:
        """盘前 AI 解读 —— 调用 Gemini 生成专业盘前分析。

        流程：
          1. 在线程池中收集 AKShare 真实市场数据
          2. 将数据拼装为 prompt 喂给 Gemini
          3. 解析 LLM 返回的结构化内容
          4. LLM 不可用或返回异常时，直接报错
        """
        # 缓存命中直接返回
        now_mono = time.monotonic()
        if _llm_digest_cache["data"] is not None and now_mono < _llm_digest_cache["expires_at"]:
            return _llm_digest_cache["data"]

        llm = get_llm_client()
        if not llm.is_configured:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="LLM 服务未配置")

        # 1. 收集数据
        preopen_data = await run_sync(self._collect_preopen_data_text)

        # 2. 构建 prompt
        system_prompt = (
            "你是一名专业的 A 股盘前分析师，每天为投资者提供盘前市场解读。"
            "请基于提供的实时市场数据，生成一段能指导盘中模拟盘观察的盘前解读。"
            "新闻可能改变全天主线，你必须把新闻催化、板块映射、风险方向和盘中验证条件讲清楚。\n\n"
            "请严格按以下 JSON 格式返回，不要添加任何其他内容：\n"
            '{\n'
            '  "headline": "一句话盘前概述（不超过 40 字）",\n'
            '  "sentiment": "bullish 或 bearish 或 neutral",\n'
            '  "key_points": ["市场结构要点1", "市场结构要点2", "市场结构要点3"],\n'
            '  "news_drivers": ["最可能影响今日市场的新闻1", "新闻2"],\n'
            '  "opportunity_sectors": ["可能受益方向1", "方向2"],\n'
            '  "risk_sectors": ["可能承压方向1", "方向2"],\n'
            '  "intraday_watch": ["盘中验证条件1", "盘中验证条件2"],\n'
            '  "simulation_plan": ["模拟盘动作建议1", "模拟盘动作建议2"]\n'
            '}\n\n'
            "要求：\n"
            "- headline 概括今日盘前核心看点\n"
            "- sentiment 基于数据判断市场情绪偏向\n"
            "- key_points 3-5 个要点，每个不超过 50 字\n"
            "- news_drivers 必须来自提供的快讯标题，不要编造新闻\n"
            "- opportunity_sectors/risk_sectors 要能映射到新闻或涨停行业分布\n"
            "- intraday_watch 要写具体验证条件，比如涨停扩散、开盘溢价、成交额承接\n"
            "- simulation_plan 要给模拟盘仓位/开仓/观望建议，但不要承诺收益"
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=f"请分析以下盘前数据：\n\n{preopen_data}"),
        ]

        # 3. 调用 Gemini
        try:
            reply = await llm.chat(messages, temperature=0.5, max_tokens=800)
            digest = self._parse_ai_digest_response(reply)
            if digest:
                _llm_digest_cache["data"] = digest
                _llm_digest_cache["expires_at"] = time.monotonic() + _LLM_CACHE_TTL
                return digest
            logger.warning("LLM 盘前解读解析失败")
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM 响应解析失败")
        except Exception as e:
            logger.error("Gemini 盘前解读生成失败: %s", e)
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="LLM 服务调用失败") from e

    @staticmethod
    def _parse_ai_digest_response(reply: str) -> AiDigest | None:
        """解析 LLM 返回的 JSON 内容为 AiDigest。"""
        import json as _json
        now = datetime.now(tz=UTC)
        calendar = _make_calendar()

        # 提取 JSON（兼容 markdown 代码块）
        text = reply.strip()
        if "```" in text:
            parts = text.split("```")
            for part in parts:
                stripped = part.strip()
                if stripped.startswith("json"):
                    stripped = stripped[4:].strip()
                if stripped.startswith("{"):
                    text = stripped
                    break

        try:
            data = _json.loads(text)
        except _json.JSONDecodeError:
            logger.warning("盘前解读 JSON 解析失败: %s", text[:200])
            return None

        if not isinstance(data, dict):
            return None

        headline = data.get("headline", "")
        sentiment = data.get("sentiment", "neutral")
        key_points = data.get("key_points", [])
        news_drivers = data.get("news_drivers", [])
        opportunity_sectors = data.get("opportunity_sectors", [])
        risk_sectors = data.get("risk_sectors", [])
        intraday_watch = data.get("intraday_watch", [])
        simulation_plan = data.get("simulation_plan", [])

        if not headline or not key_points:
            return None

        if sentiment not in ("bullish", "bearish", "neutral"):
            sentiment = "neutral"

        return AiDigest(
            digest_id=f"digest_{calendar.trade_date.isoformat()}",
            report_title=_digest_report_title(calendar.trade_date),
            headline=headline,
            interval_start=now - timedelta(hours=12),
            interval_end=now,
            generated_at=now,
            sentiment=sentiment,
            key_points=key_points,
            report_sections=_build_digest_sections(
                headline=headline,
                key_points=key_points if isinstance(key_points, list) else [],
                news_drivers=news_drivers if isinstance(news_drivers, list) else [],
                opportunity_sectors=opportunity_sectors if isinstance(opportunity_sectors, list) else [],
                risk_sectors=risk_sectors if isinstance(risk_sectors, list) else [],
                intraday_watch=intraday_watch if isinstance(intraday_watch, list) else [],
                simulation_plan=simulation_plan if isinstance(simulation_plan, list) else [],
            ),
            news_drivers=news_drivers if isinstance(news_drivers, list) else [],
            opportunity_sectors=opportunity_sectors if isinstance(opportunity_sectors, list) else [],
            risk_sectors=risk_sectors if isinstance(risk_sectors, list) else [],
            intraday_watch=intraday_watch if isinstance(intraday_watch, list) else [],
            simulation_plan=simulation_plan if isinstance(simulation_plan, list) else [],
        )

    # ─────────────── 市场指标 ───────────────

    @staticmethod
    def _build_main_index_indicators() -> list[MarketIndicator]:
        """主要指数行情：交易时段优先取实时（新浪），回退到最近收盘价（akshare 日K）。"""
        from app.integrations.akshare.client import (
            get_index_daily_bars,
            get_main_index_quotes,
        )

        # 目标 4 大指数：上证 / 深证 / 创业板 / 恒生科技（恒科暂用沪深 300 兜底）
        targets = [
            ("sh000001", "上证指数"),
            ("sz399001", "深证成指"),
            ("sz399006", "创业板指"),
            ("sh000300", "沪深300"),
        ]

        # 1. 优先尝试实时
        live = {}
        try:
            live = get_main_index_quotes()
        except Exception:
            live = {}

        indicators: list[MarketIndicator] = []
        for code, label in targets:
            value = 0.0
            change_pct = 0.0
            change_amt = 0.0
            if code in live:
                q = live[code]
                value = q.price
                change_amt = q.change
                change_pct = q.change_pct
            else:
                # 回退：取最近一日收盘（前一日为对比）
                try:
                    bars = get_index_daily_bars(symbol=code, days=2)
                    if bars:
                        latest = bars[-1]
                        value = float(latest.close)
                        if len(bars) >= 2:
                            prev_close = float(bars[-2].close)
                            change_amt = value - prev_close
                            change_pct = (change_amt / prev_close * 100) if prev_close else 0.0
                except Exception:
                    pass
            direction = "up" if change_pct > 0 else ("down" if change_pct < 0 else "flat")
            sign_amt = "+" if change_amt >= 0 else ""
            sign_pct = "+" if change_pct >= 0 else ""
            indicators.append(
                MarketIndicator(
                    indicator=f"index_{code}",
                    label=label,
                    value=round(value, 2),
                    unit="",
                    direction=direction,
                    reference=f"{sign_amt}{change_amt:.2f} ({sign_pct}{change_pct:.2f}%)",
                )
            )
        return indicators

    def list_market_indicators(self) -> list[MarketIndicator]:
        """市场指标卡 —— 主要指数（4）+ 涨停结构指标（4）。"""
        # ── 1. 主要指数 ──
        index_indicators = self._build_main_index_indicators()

        # ── 2. 涨停结构 ──
        pool = get_limit_up_pool()
        dt_pool = get_limit_down_pool()

        total_zt = len(pool)
        max_consecutive = max((s.consecutive for s in pool), default=0) if pool else 0

        # 封板率：无炸板的涨停数 / 总涨停数
        no_break = sum(1 for s in pool if s.break_count == 0) if pool else 0
        seal_ratio = round(no_break / total_zt * 100, 1) if total_zt else 0.0

        # 连板率：连板数 >= 2 的比例
        multi_board = sum(1 for s in pool if s.consecutive >= 2) if pool else 0
        consecutive_ratio = round(multi_board / total_zt * 100, 1) if total_zt else 0.0

        # 跌停家数
        total_dt = len(dt_pool)

        indicators = [
            MarketIndicator(
                indicator="highest_consecutive_limit_up",
                label="最高连板",
                value=float(max_consecutive),
                unit="板",
                direction="up" if max_consecutive >= 5 else ("down" if max_consecutive <= 2 else "flat"),
                reference=f"涨停 {total_zt} 家",
            ),
            MarketIndicator(
                indicator="limit_up_seal_ratio",
                label="封板率",
                value=seal_ratio,
                unit="%",
                direction="up" if seal_ratio > 70 else ("down" if seal_ratio < 50 else "flat"),
                reference=f"未炸板 {no_break}/{total_zt}",
            ),
            MarketIndicator(
                indicator="consecutive_limit_up_ratio",
                label="连板率",
                value=consecutive_ratio,
                unit="%",
                direction="up" if consecutive_ratio > 25 else "flat",
                reference=f"连板 {multi_board} 家",
            ),
            MarketIndicator(
                indicator="turnover_growth",
                label="涨跌停比",
                value=round(total_zt / max(total_dt, 1), 1),
                unit="倍",
                direction="up" if total_zt > total_dt * 5 else "flat",
                reference=f"涨停 {total_zt} / 跌停 {total_dt}",
            ),
        ]
        # 指数 4 个 + 结构指标 4 个 = 总 8 个
        return index_indicators + indicators

    # ─────────────── 异常波动 ───────────────

    def get_anomalies(self) -> AnomalyOverview:
        """异常波动概览 —— 从涨停池筛选高换手 + 跌停池。"""
        calendar = _make_calendar()
        pool = get_limit_up_pool()
        dt_pool = get_limit_down_pool()

        # 尾盘异动：涨停池中高换手（> 10%）或多次炸板的
        tail_moves: list[AnomalyItem] = []
        for s in pool:
            if s.turnover_ratio > 10 or s.break_count >= 2:
                tags = []
                if s.consecutive >= 2:
                    tags.append("consecutive_limit_up")
                if s.turnover_ratio > 10:
                    tags.append("high_turnover")
                tail_moves.append(AnomalyItem(
                    symbol=s.symbol,
                    name=s.name,
                    category="tail-session-move",
                    change_pct=s.change_pct,
                    turnover_ratio=s.turnover_ratio,
                    risk_tags=tags or ["high_turnover"],
                    note=f"换手 {s.turnover_ratio:.1f}%，炸板 {s.break_count} 次" if s.break_count else f"换手 {s.turnover_ratio:.1f}%，成交活跃",
                    risk_type="尾盘异动监控",
                    risk_window="盘中/尾盘",
                    is_new=s.break_count >= 2 or s.turnover_ratio >= 20,
                ))
        tail_moves = tail_moves[:5]  # 最多展示 5 条

        # 严重波动：跌停股
        severe: list[AnomalyItem] = []
        for s in dt_pool:
            severe.append(AnomalyItem(
                symbol=s.symbol,
                name=s.name,
                category="severe-volatility",
                change_pct=s.change_pct,
                turnover_ratio=s.turnover_ratio,
                risk_tags=["abnormal_volatility"],
                note=f"跌停，换手率 {s.turnover_ratio:.1f}%",
                risk_type="交易所异常波动风险",
                risk_window="连续10/30个交易日",
                is_new=True,
            ))
        severe = severe[:5]

        return AnomalyOverview(
            calendar=calendar,
            tail_session_moves=tail_moves,
            severe_volatility=severe,
        )

    # ─────────────── 涨停天梯 ───────────────

    def list_limit_up_ladder(self) -> list[LimitUpLadderItem]:
        """涨停天梯 —— 从涨停池中按连板数排序。"""
        pool = get_limit_up_pool()
        # 按连板数降序
        sorted_pool = sorted(pool, key=lambda s: (s.consecutive, s.amount), reverse=True)

        ladder: list[LimitUpLadderItem] = []
        for s in sorted_pool[:20]:
            tags = []
            if s.consecutive >= 3:
                tags.append("consecutive_limit_up")
            if s.turnover_ratio > 10:
                tags.append("high_turnover")
            if not tags:
                tags.append("high_turnover")

            ladder.append(LimitUpLadderItem(
                symbol=s.symbol,
                name=s.name,
                ladder_level=s.consecutive,
                first_seal_time=s.first_seal_time or "",
                final_seal_time=s.last_seal_time or "",
                reason=s.industry or "",
                risk_tags=tags,
            ))
        return ladder

    # ─────────────── 行业板块涨跌 ───────────────

    def list_industry_boards(self) -> list[IndustryBoardItem]:
        """行业板块涨跌 —— 同花顺行业板块实时数据。

        返回约 90 个行业板块，按涨跌幅排序。
        """
        boards = get_industry_boards()
        items = [
            IndustryBoardItem(
                name=b.name,
                change_pct=b.change_pct,
                total_amount=b.total_amount,
                net_inflow=b.net_inflow,
                rise_count=b.rise_count,
                fall_count=b.fall_count,
                leading_stock=b.leading_stock,
                leading_stock_pct=b.leading_stock_pct,
            )
            for b in boards
        ]
        # 按涨跌幅降序
        items.sort(key=lambda x: x.change_pct, reverse=True)
        return items

    # ─────────────── 涨跌榜 ───────────────

    def list_stock_rank(self, direction: str = "up") -> list[StockRankItem]:
        """涨跌榜 —— 强势股（涨）或跌停股（跌）。

        direction: "up" = 涨幅榜（强势股池前 20）, "down" = 跌幅榜（跌停池）
        """
        if direction == "down":
            pool = get_limit_down_pool()
            items = [
                StockRankItem(
                    symbol=s.symbol,
                    name=s.name,
                    change_pct=s.change_pct,
                    price=s.price,
                    amount=s.amount,
                    turnover_ratio=s.turnover_ratio,
                    industry="",
                    reason="跌停",
                )
                for s in pool
            ]
            items.sort(key=lambda x: x.change_pct)
        else:
            pool = get_strong_pool()
            items = [
                StockRankItem(
                    symbol=s.symbol,
                    name=s.name,
                    change_pct=s.change_pct,
                    price=s.price,
                    amount=s.amount,
                    turnover_ratio=s.turnover_ratio,
                    industry="",
                    reason="强势",
                )
                for s in pool[:20]
            ]
            items.sort(key=lambda x: x.change_pct, reverse=True)
        return items

    # ─────────────── 趋势数据 ───────────────

    def collect_market_snapshot_payload(self, trade_date: date | None = None) -> dict[str, Any]:
        """采集一份真实市场结构快照，供落库和兜底趋势共用。"""
        calendar = _make_calendar()
        snapshot_date = trade_date or calendar.trade_date
        pool = get_limit_up_pool()
        dt_pool = get_limit_down_pool()
        strong = get_strong_pool()

        total_zt = len(pool)
        no_break = sum(1 for s in pool if int(getattr(s, "break_count", 0) or 0) == 0) if pool else 0
        industry_counter = Counter(
            getattr(s, "industry", "") for s in pool if getattr(s, "industry", "")
        )

        return {
            "trade_date": snapshot_date,
            "snapshot_at": datetime.now(tz=UTC),
            "limit_up_count": total_zt,
            "limit_down_count": len(dt_pool),
            "consecutive_limit_up_count": sum(1 for s in pool if int(getattr(s, "consecutive", 0) or 0) >= 2),
            "highest_consecutive": max((int(getattr(s, "consecutive", 0) or 0) for s in pool), default=0),
            "strong_count": len(strong),
            "break_count": sum(1 for s in pool if int(getattr(s, "break_count", 0) or 0) > 0),
            "seal_ratio": round(no_break / total_zt * 100, 2) if total_zt else 0.0,
            "top_industries": [
                {"name": industry, "limit_up_count": count}
                for industry, count in industry_counter.most_common(8)
            ],
        }

    async def async_record_market_snapshot(
        self,
        session: AsyncSession,
        trade_date: date | None = None,
    ) -> PreopenMarketSnapshot:
        """写入或更新当天盘前市场快照。"""
        payload = await run_sync(self.collect_market_snapshot_payload, trade_date)
        result = await session.execute(
            select(PreopenMarketSnapshot).where(
                PreopenMarketSnapshot.trade_date == payload["trade_date"]
            )
        )
        snapshot = result.scalar_one_or_none()
        if snapshot is None:
            snapshot = PreopenMarketSnapshot(id=f"pm_{uuid4().hex[:12]}", **payload)
            session.add(snapshot)
        else:
            for key, value in payload.items():
                setattr(snapshot, key, value)
        await session.flush()
        return snapshot

    @staticmethod
    def _trend_overview_from_snapshots(
        rows: list[PreopenMarketSnapshot],
        *,
        requested_days: int,
    ) -> TrendOverview:
        calendar = _make_calendar()
        ordered = sorted(rows, key=lambda row: row.trade_date)
        return TrendOverview(
            calendar=calendar,
            window_days=min(requested_days, len(ordered)) if ordered else 0,
            series=[
                TrendSeries(
                    metric="daily_limit_up_count",
                    label="每日涨停家数",
                    unit="家",
                    points=[
                        TrendPoint(trade_date=row.trade_date, value=row.limit_up_count)
                        for row in ordered
                    ],
                ),
                TrendSeries(
                    metric="daily_limit_down_count",
                    label="每日跌停家数",
                    unit="家",
                    points=[
                        TrendPoint(trade_date=row.trade_date, value=row.limit_down_count)
                        for row in ordered
                    ],
                ),
                TrendSeries(
                    metric="consecutive_limit_up_count",
                    label="连板家数",
                    unit="家",
                    points=[
                        TrendPoint(trade_date=row.trade_date, value=row.consecutive_limit_up_count)
                        for row in ordered
                    ],
                ),
            ],
        )

    async def async_get_trends(self, session: AsyncSession, *, days: int = 15) -> TrendOverview:
        """从落库快照读取多日趋势，并先确保最近交易日已有真实快照。"""
        await self.async_record_market_snapshot(session)
        result = await session.execute(
            select(PreopenMarketSnapshot)
            .order_by(PreopenMarketSnapshot.trade_date.desc())
            .limit(days)
        )
        rows = list(result.scalars().all())
        return self._trend_overview_from_snapshots(rows, requested_days=days)

    def get_trends(self) -> TrendOverview:
        """趋势兜底：只返回最新真实快照点，不伪造历史。"""
        calendar = _make_calendar()
        payload = self.collect_market_snapshot_payload(calendar.trade_date)

        return TrendOverview(
            calendar=calendar,
            window_days=1,
            series=[
                TrendSeries(
                    metric="daily_limit_up_count",
                    label="每日涨停家数",
                    unit="家",
                    points=[TrendPoint(trade_date=calendar.trade_date, value=payload["limit_up_count"])],
                ),
                TrendSeries(
                    metric="daily_limit_down_count",
                    label="每日跌停家数",
                    unit="家",
                    points=[TrendPoint(trade_date=calendar.trade_date, value=payload["limit_down_count"])],
                ),
                TrendSeries(
                    metric="consecutive_limit_up_count",
                    label="连板家数",
                    unit="家",
                    points=[
                        TrendPoint(
                            trade_date=calendar.trade_date,
                            value=payload["consecutive_limit_up_count"],
                        )
                    ],
                ),
            ],
        )

    @staticmethod
    def _latest_trade_dates(days: int, ref_date: date | None = None) -> list[date]:
        """返回最近 N 个交易日（简单按工作日回溯）。"""
        dates: list[date] = []
        cursor = ref_date or date.today()
        while len(dates) < days:
            if cursor.weekday() < 5:
                dates.append(cursor)
            cursor -= timedelta(days=1)
        return list(reversed(dates))
