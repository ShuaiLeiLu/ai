"""
题材掘金 · 事件驱动服务。

数据侧只使用 AKShare 涨停池、行业板块和实时快讯生成当日快照。
外部数据不可用或题材未命中真实快照时返回空列表/404，避免用样例内容伪装成市场数据。
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.client import (
    IndustryBoard,
    LimitUpStock,
    LiveNewsItem,
    get_industry_boards,
    get_limit_up_pool,
    get_live_news_merged,
)
from app.modules.event_driven.schemas import (
    AccessStatus,
    AnchorRecommendItem,
    ConsensusBreakdown,
    CoreTarget,
    CoreTargetGroup,
    EventDrivenChain,
    ExpectationGap,
    HiddenLogicItem,
    MarketStory,
    MarketStorySegment,
    PastEvent,
    TheySayBoard,
    ThemeDetail,
    ThemeListItem,
    UnlockResult,
)
from app.models.billing import BatteryLedger
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


# ---------- 题材列表（31 个） ----------
THEMES: list[ThemeListItem] = [
    ThemeListItem(id="medicine", rank=1, name="医药", status="today_hot", limit_up_count=5, event_count=5),
    ThemeListItem(id="aerospace", rank=2, name="航天", status="today_hot", limit_up_count=4, event_count=3),
    ThemeListItem(id="auto_chain", rank=3, name="汽车产业链", status="today_hot", limit_up_count=4, event_count=4),
    ThemeListItem(id="chemical", rank=4, name="化工", status="today_hot", limit_up_count=6, event_count=11),
    ThemeListItem(id="semiconductor", rank=5, name="半导体产业链", status="today_hot", limit_up_count=13, event_count=2),
    ThemeListItem(id="robotics", rank=6, name="机器人", status="today_hot", limit_up_count=11, event_count=7),
    ThemeListItem(id="pcb", rank=7, name="PCB 产业链", status="today_hot", limit_up_count=26, event_count=2),
    ThemeListItem(id="liquid_cooling", rank=8, name="液冷", status="today_hot", limit_up_count=4, event_count=2),
    ThemeListItem(id="mlcc", rank=9, name="MLCC/电容", status="today_hot", limit_up_count=12, event_count=3),
    ThemeListItem(id="compute_rental", rank=10, name="算力租赁", status="today_hot", limit_up_count=3, event_count=4),
    ThemeListItem(id="optical_comm", rank=11, name="光通信", status="today_hot", limit_up_count=5, event_count=2),
    ThemeListItem(id="cro_cdmo", rank=12, name="CRO/CDMO", status="yesterday_hot", limit_up_count=3, event_count=4),
    ThemeListItem(id="ai_app", rank=13, name="AI 应用", status="yesterday_hot", limit_up_count=4, event_count=6),
    ThemeListItem(id="storage", rank=14, name="存储芯片", status="yesterday_hot", limit_up_count=2, event_count=3),
    ThemeListItem(id="solid_state_battery", rank=15, name="固态电池", status="yesterday_hot", limit_up_count=2, event_count=2),
    ThemeListItem(id="brain_computer", rank=16, name="脑机接口", status="yesterday_hot", limit_up_count=2, event_count=3),
    ThemeListItem(id="quantum", rank=17, name="量子科技", status="waiting", limit_up_count=1, event_count=2),
    ThemeListItem(id="commercial_aerospace", rank=18, name="商业航天", status="waiting", limit_up_count=1, event_count=3),
    ThemeListItem(id="data_center", rank=19, name="数据中心", status="waiting", limit_up_count=1, event_count=2),
    ThemeListItem(id="nuclear_fusion", rank=20, name="可控核聚变", status="waiting", limit_up_count=0, event_count=4),
    ThemeListItem(id="defense", rank=21, name="军工", status="waiting", limit_up_count=1, event_count=2),
    ThemeListItem(id="rare_earth", rank=22, name="稀土永磁", status="waiting", limit_up_count=1, event_count=2),
    ThemeListItem(id="hydrogen", rank=23, name="氢能", status="lurking", limit_up_count=0, event_count=1),
    ThemeListItem(id="low_altitude", rank=24, name="低空经济", status="lurking", limit_up_count=0, event_count=2),
    ThemeListItem(id="ev_charging", rank=25, name="充电桩", status="lurking", limit_up_count=0, event_count=1),
    ThemeListItem(id="state_owned", rank=26, name="国企改革", status="lurking", limit_up_count=0, event_count=2),
    ThemeListItem(id="cross_border_ec", rank=27, name="跨境电商", status="lurking", limit_up_count=0, event_count=1),
    ThemeListItem(id="silver_economy", rank=28, name="银发经济", status="lurking", limit_up_count=0, event_count=1),
    ThemeListItem(id="education", rank=29, name="教育", status="lurking", limit_up_count=0, event_count=1),
    ThemeListItem(id="agriculture", rank=30, name="农业种植", status="lurking", limit_up_count=0, event_count=1),
    ThemeListItem(id="culture_media", rank=31, name="文化传媒", status="lurking", limit_up_count=0, event_count=2),
]


THEME_KEYWORDS: dict[str, list[str]] = {
    "medicine": ["医药", "医疗", "创新药", "CRO", "CDMO", "生物", "疫苗", "中药"],
    "aerospace": ["航天", "卫星", "航空", "军工"],
    "auto_chain": ["汽车", "整车", "零部件", "智能驾驶", "新能源车", "特斯拉"],
    "chemical": ["化工", "化学", "材料", "农化", "钛白粉"],
    "semiconductor": ["半导体", "芯片", "电子", "集成电路", "设备", "材料"],
    "robotics": ["机器人", "自动化", "机械", "人形机器人"],
    "pcb": ["PCB", "印制电路", "电子元件", "覆铜板"],
    "liquid_cooling": ["液冷", "散热", "数据中心"],
    "mlcc": ["MLCC", "电容", "被动元件", "电子元件"],
    "compute_rental": ["算力", "云计算", "数据中心", "服务器"],
    "optical_comm": ["光通信", "光模块", "通信设备", "CPO"],
    "cro_cdmo": ["CRO", "CDMO", "医药外包", "创新药"],
    "ai_app": ["AI", "人工智能", "软件", "传媒", "应用"],
    "storage": ["存储", "DRAM", "NAND", "芯片"],
    "solid_state_battery": ["固态电池", "电池", "锂电"],
    "brain_computer": ["脑机", "医疗器械", "人工智能"],
    "quantum": ["量子", "通信", "计算"],
    "commercial_aerospace": ["商业航天", "卫星", "航天"],
    "data_center": ["数据中心", "IDC", "服务器", "算力"],
    "nuclear_fusion": ["核聚变", "核电", "电力设备"],
    "defense": ["军工", "国防", "航天", "航空"],
    "rare_earth": ["稀土", "永磁", "小金属"],
    "hydrogen": ["氢能", "燃料电池"],
    "low_altitude": ["低空", "飞行汽车", "无人机", "航空"],
    "ev_charging": ["充电桩", "电力设备", "新能源"],
    "state_owned": ["国企改革", "中字头", "央企"],
    "cross_border_ec": ["跨境电商", "电商", "贸易"],
    "silver_economy": ["银发", "养老", "医疗"],
    "education": ["教育", "培训"],
    "agriculture": ["农业", "种植", "种业"],
    "culture_media": ["文化传媒", "传媒", "游戏", "影视"],
}


@dataclass(frozen=True)
class MarketSnapshot:
    pool: list[LimitUpStock]
    boards: list[IndustryBoard]
    news: list[LiveNewsItem]
    generated_at: datetime


def _theme_terms(theme: ThemeListItem) -> list[str]:
    terms = [theme.name]
    terms.extend(THEME_KEYWORDS.get(theme.id, []))
    for suffix in ("产业链", "板块", "概念"):
        if theme.name.endswith(suffix):
            terms.append(theme.name.removesuffix(suffix))
    return [term for term in dict.fromkeys(terms) if term]


def _matches_any(text: str, terms: list[str]) -> bool:
    upper_text = text.upper()
    return any(term.upper() in upper_text for term in terms)


def _stock_matches_theme(stock: LimitUpStock, theme: ThemeListItem) -> bool:
    text = f"{stock.industry} {stock.name}"
    return _matches_any(text, _theme_terms(theme))


def _board_matches_theme(board: IndustryBoard, theme: ThemeListItem) -> bool:
    text = f"{board.name} {board.leading_stock}"
    return _matches_any(text, _theme_terms(theme))


def _news_matches_theme(item: LiveNewsItem, theme: ThemeListItem) -> bool:
    text = f"{item.title} {item.content}"
    return _matches_any(text, _theme_terms(theme))


def _load_market_snapshot() -> MarketSnapshot:
    try:
        pool = get_limit_up_pool()
    except Exception:
        logger.exception("题材掘金获取涨停池失败")
        pool = []
    try:
        boards = get_industry_boards()
    except Exception:
        logger.exception("题材掘金获取行业板块失败")
        boards = []
    try:
        news = get_live_news_merged()
    except Exception:
        logger.exception("题材掘金获取实时快讯失败")
        news = []
    return MarketSnapshot(pool=pool, boards=boards, news=news, generated_at=datetime.now(timezone.utc))


def _matched_board(theme: ThemeListItem, boards: list[IndustryBoard]) -> IndustryBoard | None:
    return next((board for board in boards if _board_matches_theme(board, theme)), None)


def _status_from_market(seed: ThemeListItem, limit_up_count: int, board: IndustryBoard | None) -> str:
    change_pct = board.change_pct if board else 0.0
    if limit_up_count >= 3 or change_pct >= 2.5:
        return "today_hot"
    if limit_up_count > 0 or change_pct >= 1.0:
        return "yesterday_hot"
    if change_pct <= -1.5:
        return "waiting"
    return "lurking"


def _format_amount_yi(value: float) -> str:
    if value <= 0:
        return "成交额待同步"
    return f"{value / 100000000:.1f} 亿"


def _format_pct(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _build_they_say_from_market(snapshot: MarketSnapshot) -> TheySayBoard:
    pool = snapshot.pool
    boards = snapshot.boards
    total_limit_up = len(pool)
    multi_board = sum(1 for item in pool if item.consecutive >= 2)
    avg_board_change = sum(board.change_pct for board in boards[:8]) / max(len(boards[:8]), 1) if boards else 0.0

    if total_limit_up >= 60 or multi_board >= 15 or avg_board_change >= 1.2:
        sentiment_direction = "bullish"
        sentiment_label = "偏多 · 强共识"
        bullish, neutral, bearish = 6, 1, 1
        confidence = 8.0
        cycle = "发酵期"
    elif total_limit_up <= 25 and avg_board_change < -0.5:
        sentiment_direction = "bearish"
        sentiment_label = "偏空 · 防守共识"
        bullish, neutral, bearish = 2, 2, 4
        confidence = 6.7
        cycle = "退潮期"
    else:
        sentiment_direction = "neutral"
        sentiment_label = "中性 · 有分歧"
        bullish, neutral, bearish = 3, 3, 2
        confidence = 6.1
        cycle = "观察期"

    industry_counter = Counter(item.industry for item in pool if item.industry)
    top_industries = [name for name, _ in industry_counter.most_common(3)]
    hot_text = "、".join(top_industries) if top_industries else "暂无明确涨停主线"
    summary = (
        f"当日涨停 {total_limit_up} 家，连板 {multi_board} 家，资金主攻 {hot_text}。"
        f"行业板块均值约 {_format_pct(avg_board_change)}，关注高位股承接和低位扩散。"
    )

    return TheySayBoard(
        generated_at=snapshot.generated_at,
        sentiment_direction=sentiment_direction,
        sentiment_label=sentiment_label,
        bullish_count=bullish,
        neutral_count=neutral,
        bearish_count=bearish,
        confidence=confidence,
        cycle=cycle,
        cycle_note=f"基于涨停池和前 8 行业板块实时快照 · 连板 {multi_board} 家",
        summary=summary,
    )


def _enrich_theme_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> ThemeListItem:
    matched_stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    board = _matched_board(theme, snapshot.boards)
    matched_news = [item for item in snapshot.news if _news_matches_theme(item, theme)]
    limit_up_count = len(matched_stocks)
    event_count = len(matched_news) + (1 if matched_stocks or board else 0)
    return ThemeListItem(
        id=theme.id,
        rank=theme.rank,
        name=theme.name,
        status=_status_from_market(theme, limit_up_count, board),
        limit_up_count=limit_up_count,
        event_count=event_count,
    )


def _theme_has_market_signal(theme: ThemeListItem, snapshot: MarketSnapshot) -> bool:
    """只有命中真实涨停池、行业板块或快讯的题材才进入题材掘金。"""
    return (
        any(_stock_matches_theme(stock, theme) for stock in snapshot.pool)
        or _matched_board(theme, snapshot.boards) is not None
        or any(_news_matches_theme(item, theme) for item in snapshot.news)
    )


def _market_themes(snapshot: MarketSnapshot) -> list[ThemeListItem]:
    if not snapshot.pool and not snapshot.boards and not snapshot.news:
        return []

    items = [_enrich_theme_from_market(theme, snapshot) for theme in THEMES]
    items = [item for item in items if _theme_has_market_signal(item, snapshot)]

    ranked = sorted(
        items,
        key=lambda item: (
            0 if item.status == "today_hot" else 1 if item.status == "yesterday_hot" else 2 if item.status == "waiting" else 3,
            -item.limit_up_count,
            item.rank,
        ),
    )
    return [
        ThemeListItem(
            id=item.id,
            rank=index,
            name=item.name,
            status=item.status,
            limit_up_count=item.limit_up_count,
            event_count=item.event_count,
        )
        for index, item in enumerate(ranked, start=1)
    ]


def _today_label(now: datetime) -> str:
    return f"今天 · {now.month}/{now.day}"


def _news_past_events(theme: ThemeListItem, snapshot: MarketSnapshot, limit: int = 3) -> list[PastEvent]:
    matched = [item for item in snapshot.news if _news_matches_theme(item, theme)]
    events: list[PastEvent] = []
    for index, item in enumerate(matched[:limit], start=1):
        events.append(
            PastEvent(
                id=f"{theme.id}-news-{index}",
                title=item.title,
                description=(item.content or item.title)[:160],
                impact="high" if index == 1 else "medium",
                category="policy" if any(word in item.title for word in ("政策", "国常会", "发改委", "工信部")) else "industry",
                occurred_at=_today_label(snapshot.generated_at),
                source=item.source,
            )
        )
    return events


def _stock_past_events(theme: ThemeListItem, stocks: list[LimitUpStock], snapshot: MarketSnapshot) -> list[PastEvent]:
    events: list[PastEvent] = []
    for index, stock in enumerate(stocks[:3], start=1):
        title = f"{stock.name}涨停，带动{theme.name}情绪升温"
        description = (
            f"{stock.name}({stock.symbol}) {_format_pct(stock.change_pct)}，"
            f"{stock.consecutive}连板，换手率 {stock.turnover_ratio:.1f}%，"
            f"成交额 {_format_amount_yi(stock.amount)}。"
        )
        events.append(
            PastEvent(
                id=f"{theme.id}-limit-{index}",
                title=title,
                description=description,
                impact="high" if stock.consecutive >= 2 else "medium",
                category="sentiment",
                occurred_at=_today_label(snapshot.generated_at),
                source="东方财富涨停池",
            )
        )
    return events


def _core_target_groups(theme: ThemeListItem, stocks: list[LimitUpStock], board: IndustryBoard | None) -> list[CoreTargetGroup]:
    sorted_stocks = sorted(stocks, key=lambda item: (item.consecutive, item.amount), reverse=True)

    def stock_target(stock: LimitUpStock) -> CoreTarget:
        metric = f"{stock.consecutive} 板" if stock.consecutive > 1 else _format_pct(stock.change_pct)
        note_parts = [stock.industry or theme.name]
        if stock.break_count:
            note_parts.append(f"炸板 {stock.break_count} 次")
        if stock.first_seal_time:
            note_parts.append(f"首封 {stock.first_seal_time}")
        return CoreTarget(symbol=stock.symbol, name=stock.name, metric=metric, note=" · ".join(note_parts))

    sentiment_items = [stock_target(stock) for stock in sorted_stocks[:2]]
    logic_items = [stock_target(stock) for stock in sorted_stocks[2:4]]
    trend_items = [stock_target(stock) for stock in sorted_stocks[4:6]]

    if not sentiment_items and board is not None and board.leading_stock:
        sentiment_items = [
            CoreTarget(
                symbol="---",
                name=board.leading_stock,
                metric=_format_pct(board.leading_stock_pct),
                note=f"{board.name}领涨 · 板块 {_format_pct(board.change_pct)}",
            )
        ]

    return [
        CoreTargetGroup(role="sentiment_core", label="情绪核心", items=sentiment_items),
        CoreTargetGroup(role="logic_core", label="逻辑核心", items=logic_items),
        CoreTargetGroup(role="trend_anchor", label="趋势中军", items=trend_items),
    ]


def _event_chain_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> EventDrivenChain:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    board = _matched_board(theme, snapshot.boards)
    past_events = _news_past_events(theme, snapshot) + _stock_past_events(theme, stocks, snapshot)
    if not past_events:
        past_events = [
            PastEvent(
                id=f"{theme.id}-board",
                title=f"{theme.name}板块进入观察窗口",
                description=(
                    f"{board.name}板块涨跌幅 {_format_pct(board.change_pct)}，领涨股 {board.leading_stock}。"
                    if board
                    else "暂未捕捉到明确快讯或涨停扩散，继续观察资金是否形成共振。"
                ),
                impact="medium",
                category="industry",
                occurred_at=_today_label(snapshot.generated_at),
                source="同花顺行业板块" if board else "题材掘金快照",
            )
        ]

    return EventDrivenChain(
        past_events=past_events[:5],
        future_expectations=[],
        core_target_groups=_core_target_groups(theme, stocks, board),
    )


def _expectation_gaps_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> list[ExpectationGap]:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    board = _matched_board(theme, snapshot.boards)
    gaps: list[ExpectationGap] = []
    if board and board.change_pct > 0 and len(stocks) >= 2:
        gaps.append(
            ExpectationGap(
                id=f"{theme.id}-gap-up",
                direction="undervalued",
                target_label=theme.name,
                title=f"板块涨幅与涨停扩散同步，短线认知仍在修正",
                magnitude_pct=round(max(board.change_pct * 6, len(stocks) * 3.0), 1),
                reasoning=f"{board.name}板块 {_format_pct(board.change_pct)}，涨停池匹配 {len(stocks)} 家，说明资金已从单点向板块扩散。",
            )
        )
    if stocks and any(stock.break_count > 0 for stock in stocks):
        broken = sum(1 for stock in stocks if stock.break_count > 0)
        gaps.append(
            ExpectationGap(
                id=f"{theme.id}-gap-risk",
                direction="overvalued",
                target_label="高位标的",
                title="炸板次数抬升，追高赔率下降",
                magnitude_pct=round(-broken * 8.0, 1),
                reasoning=f"匹配涨停股中有 {broken} 家出现炸板，说明一致预期开始松动。",
            )
        )
    return gaps


def _market_story_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> MarketStory:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    board = _matched_board(theme, snapshot.boards)
    stock_names = "、".join(stock.name for stock in stocks[:3]) or (board.leading_stock if board else theme.name)
    today = [
        MarketStorySegment(
            time_range="09:30 - 10:00",
            headline="开盘定方向 · 观察核心标的封单",
            narrative=f"{stock_names} 的开盘强弱决定 {theme.name} 是否能从单点催化扩散成板块共振。",
        ),
        MarketStorySegment(
            time_range="10:00 - 11:30",
            headline="扩散验证 · 看跟风涨停数量",
            narrative=f"当前匹配涨停 {len(stocks)} 家，若同题材继续增加，说明短线资金认可度提升。",
        ),
        MarketStorySegment(
            time_range="13:00 - 15:00",
            headline="尾盘确认 · 防止高位回落",
            narrative=(
                f"板块涨幅 {_format_pct(board.change_pct)}，领涨 {board.leading_stock}，尾盘需观察封板质量。"
                if board
                else "尾盘重点观察封单衰减和炸板次数，避免追随已经透支的方向。"
            ),
        ),
    ]
    return MarketStory(today=today, yesterday=[])


def _hidden_logic_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> list[HiddenLogicItem]:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    industries = [name for name, _ in Counter(stock.industry for stock in stocks if stock.industry).most_common(3)]
    if not industries:
        return []
    return [
        HiddenLogicItem(
            id=f"{theme.id}-hidden-1",
            title=f"{industries[0]} ⟶ {theme.name}资金共振",
            description=f"涨停池映射显示 {theme.name} 与 {industries[0]} 的资金流向存在同步，适合观察是否形成二阶扩散。",
            tags=industries,
        ),
        HiddenLogicItem(
            id=f"{theme.id}-hidden-2",
            title="快讯催化 ⟶ 涨停池验证",
            description="将实时快讯与涨停池交叉验证，能过滤只有消息没有资金跟随的弱题材。",
            tags=[theme.name, "快讯", "涨停池"],
        ),
    ]


def _anchor_recommendations_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> list[AnchorRecommendItem]:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    names = [stock.name for stock in stocks[:3]]
    if not names:
        return []
    return [
        AnchorRecommendItem(
            horizon="today",
            label="最具爆发潜力",
            title=f"{theme.name}板块扩散",
            description=f"涨停池匹配 {len(stocks)} 家，优先观察核心标的封单质量和低位补涨扩散。",
            related_symbols=names,
        ),
        AnchorRecommendItem(
            horizon="this_week",
            label="本周主线观察",
            title=f"{theme.name}事件链延续",
            description="若快讯催化、行业涨幅和连板高度三者共振，题材有望进入持续跟踪池。",
            related_symbols=names[:2],
        ),
    ]


def _consensus_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> ConsensusBreakdown:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    board = _matched_board(theme, snapshot.boards)
    if len(stocks) >= 3 or (board and board.change_pct >= 2):
        return ConsensusBreakdown(bullish=5, neutral=2, bearish=1, watch=0, summary="强共识 · 涨停池已扩散")
    if stocks or (board and board.change_pct > 0):
        return ConsensusBreakdown(bullish=3, neutral=3, bearish=1, watch=1, summary="中等共识 · 等待二次确认")
    return ConsensusBreakdown(bullish=2, neutral=3, bearish=1, watch=2, summary="有分歧 · 暂未形成主线")


def _detail_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> ThemeDetail:
    enriched = _enrich_theme_from_market(theme, snapshot)
    return ThemeDetail(
        id=enriched.id,
        name=enriched.name,
        status=enriched.status,
        limit_up_count=enriched.limit_up_count,
        researcher_count=0,
        they_say=_build_they_say_from_market(snapshot),
        event_chain=_event_chain_from_market(enriched, snapshot),
        expectation_gaps=_expectation_gaps_from_market(enriched, snapshot),
        market_story=_market_story_from_market(enriched, snapshot),
        hidden_logic=_hidden_logic_from_market(enriched, snapshot),
        anchor_recommendations=_anchor_recommendations_from_market(enriched, snapshot),
        scenarios=[],
        opinions=[],
        consensus=_consensus_from_market(enriched, snapshot),
    )


class EventDrivenService:
    """题材掘金业务服务。"""

    unlock_cost = 200

    def list_themes(self) -> list[ThemeListItem]:
        snapshot = _load_market_snapshot()
        return _market_themes(snapshot)

    def get_theme(self, theme_id: str) -> ThemeDetail | None:
        for theme in THEMES:
            if theme.id == theme_id:
                snapshot = _load_market_snapshot()
                if not _theme_has_market_signal(theme, snapshot):
                    return None
                return _detail_from_market(theme, snapshot)
        return None

    def they_say(self) -> TheySayBoard:
        snapshot = _load_market_snapshot()
        if snapshot.pool or snapshot.boards:
            return _build_they_say_from_market(snapshot)
        return TheySayBoard(
            generated_at=snapshot.generated_at,
            sentiment_direction="neutral",
            sentiment_label="暂无真实快照",
            bullish_count=0,
            neutral_count=0,
            bearish_count=0,
            confidence=0,
            cycle="等待数据",
            cycle_note="未获取到涨停池或行业板块快照",
            summary="当前未获取到真实市场快照，请稍后重试或检查数据源连接。",
        )

    def access_status(self) -> AccessStatus:
        return AccessStatus(vip=False, unlocked_today=False, battery_balance=26, unlock_cost=self.unlock_cost)

    async def async_access_status(self, session: AsyncSession | None, user_id: str | None) -> AccessStatus:
        if not session or not user_id:
            return self.access_status()

        user = await UserRepository(session).get_by_id(user_id)
        if not user:
            return self.access_status()

        vip = str(user.membership_level).upper().startswith("VIP")
        unlocked_today = vip or await self._has_today_unlock(session, user_id)
        return AccessStatus(
            vip=vip,
            unlocked_today=unlocked_today,
            battery_balance=user.battery_balance,
            unlock_cost=self.unlock_cost,
        )

    def unlock(self) -> UnlockResult:
        return UnlockResult(
            success=True,
            battery_balance=max(0, 26 - self.unlock_cost),
            unlocked_until=datetime.now(timezone.utc) + timedelta(hours=24),
        )

    async def async_unlock(self, session: AsyncSession | None, user_id: str | None) -> UnlockResult:
        if not session or not user_id:
            return self.unlock()

        user_repo = UserRepository(session)
        user = await user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")

        if str(user.membership_level).upper().startswith("VIP") or await self._has_today_unlock(session, user_id):
            return UnlockResult(
                success=True,
                battery_balance=user.battery_balance,
                unlocked_until=self._today_unlock_until(),
            )

        if user.battery_balance < self.unlock_cost:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"算力不足，解锁需要 {self.unlock_cost} 算力，当前余额 {user.battery_balance}",
            )

        await user_repo.update_battery(user, -self.unlock_cost)
        session.add(
            BatteryLedger(
                id=f"bl_{uuid4().hex[:12]}",
                user_id=user_id,
                change=-self.unlock_cost,
                balance_after=user.battery_balance,
                reason="题材掘金单日解锁",
            )
        )
        await session.commit()
        return UnlockResult(
            success=True,
            battery_balance=user.battery_balance,
            unlocked_until=self._today_unlock_until(),
        )

    async def _has_today_unlock(self, session: AsyncSession, user_id: str) -> bool:
        from sqlalchemy import select

        day_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(BatteryLedger.id)
            .where(
                BatteryLedger.user_id == user_id,
                BatteryLedger.reason == "题材掘金单日解锁",
                BatteryLedger.created_at >= day_start,
            )
            .limit(1)
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    @staticmethod
    def _today_unlock_until() -> datetime:
        now = datetime.now(timezone.utc)
        return (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
