"""
题材掘金 · 事件驱动服务。

设计稿需要完整的 8 大模块；数据侧优先用 AKShare 涨停池、行业板块和实时快讯
生成当日快照，外部数据不可用时再回退到设计稿结构化样例，避免页面空白。
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
    FutureExpectation,
    HiddenLogicItem,
    MarketStory,
    MarketStorySegment,
    PastEvent,
    ResearcherOpinion,
    Scenario,
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


# ---------- 它们说（顶部 Hero） ----------
def build_they_say(generated_at: datetime | None = None) -> TheySayBoard:
    return TheySayBoard(
        generated_at=generated_at or datetime.now(timezone.utc),
        sentiment_direction="bullish",
        sentiment_label="偏多 · 强共识",
        bullish_count=6,
        neutral_count=1,
        bearish_count=1,
        confidence=7.8,
        cycle="发酵期",
        cycle_note="由 启动 切换 · 已持续 3 日",
        summary=(
            "PCB / 半导体接力发酵，板块轮动加速；机器人、液冷为外围扩散方向。"
            "注意明日高位股回吐压力。"
        ),
    )


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
    limit_up_count = len(matched_stocks) if snapshot.pool else theme.limit_up_count
    event_count = max(len(matched_news), 1 if matched_stocks else 0) if snapshot.news or snapshot.pool else theme.event_count
    return ThemeListItem(
        id=theme.id,
        rank=theme.rank,
        name=theme.name,
        status=_status_from_market(theme, limit_up_count, board),
        limit_up_count=limit_up_count,
        event_count=event_count,
    )


def _market_themes(snapshot: MarketSnapshot) -> list[ThemeListItem]:
    items = [_enrich_theme_from_market(theme, snapshot) for theme in THEMES]
    if not snapshot.pool and not snapshot.boards:
        return items

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

    if not logic_items:
        logic_items = [CoreTarget(symbol="---", name=f"{theme.name}龙头", metric="待确认", note="等待涨停池扩散确认")]
    if not trend_items:
        trend_items = [CoreTarget(symbol="---", name=f"{theme.name}中军", metric="跟踪中", note="观察成交额和板块涨幅")]

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

    leading_names = "、".join(stock.name for stock in stocks[:3]) or (board.leading_stock if board else theme.name)
    future_expectations = [
        FutureExpectation(
            id=f"{theme.id}-catalyst",
            kind="catalyst",
            title=f"{theme.name}扩散确认",
            description=f"观察 {leading_names} 开盘承接、连板高度和跟风涨停数量，若扩散至 3 家以上说明题材继续发酵。",
            when="下一交易日",
        ),
        FutureExpectation(
            id=f"{theme.id}-risk",
            kind="risk",
            title="高位分歧与资金切换",
            description="若核心标的封单快速衰减或炸板次数上升，说明资金可能转向低位补涨或防御方向。",
            when="盘中 10:30 前",
        ),
    ]

    return EventDrivenChain(
        past_events=past_events[:5],
        future_expectations=future_expectations,
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
    return gaps or [
        ExpectationGap(
            id=f"{theme.id}-gap-default",
            direction="undervalued",
            target_label=theme.name,
            title="二线标的存在补涨预期差",
            magnitude_pct=12.5,
            reasoning="一线龙头被充分定价后，资金可能向成交额改善的二线标的切换。",
        )
    ]


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
        industries = [theme.name]
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


def _scenarios_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> list[Scenario]:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    board = _matched_board(theme, snapshot.boards)
    hot_probability = 0.45 if len(stocks) >= 3 else 0.30
    if board and board.change_pct >= 2:
        hot_probability += 0.10
    neutral_probability = max(0.25, 0.70 - hot_probability)
    cold_probability = round(max(0.10, 1 - hot_probability - neutral_probability), 2)
    return [
        Scenario(
            kind="optimistic",
            label=f"乐观 · {hot_probability:.0%}",
            probability=round(hot_probability, 2),
            title=f"{theme.name}继续扩散",
            strategy="低吸核心回封标的，避免追高弱跟风。",
            key_observation="开盘 30 分钟涨停扩散数量和核心封单金额",
        ),
        Scenario(
            kind="neutral",
            label=f"震荡 · {neutral_probability:.0%}",
            probability=round(neutral_probability, 2),
            title="高低切换，板块内部轮动",
            strategy="控制仓位，等分歧后的二次确认。",
            key_observation="10 点前强弱分化和成交额承接",
        ),
        Scenario(
            kind="pessimistic",
            label=f"悲观 · {cold_probability:.0%}",
            probability=cold_probability,
            title="封单衰减，题材降温",
            strategy="回避高位股，转向低波动或防御方向。",
            key_observation="炸板次数、跌停扩散和板块涨跌幅",
        ),
    ]


def _opinions_from_market(theme: ThemeListItem, snapshot: MarketSnapshot) -> list[ResearcherOpinion]:
    stocks = [stock for stock in snapshot.pool if _stock_matches_theme(stock, theme)]
    board = _matched_board(theme, snapshot.boards)
    bullish = len(stocks) >= 3 or bool(board and board.change_pct > 1.5)
    cautious = any(stock.break_count > 0 for stock in stocks)
    return [
        ResearcherOpinion(
            id=f"{theme.id}-op-afa",
            researcher_id="afa",
            researcher_name="情绪超短·阿发",
            avatar_initial="发",
            avatar_color="up",
            stance="bullish" if bullish else "watch",
            confidence_pct=86 if bullish else 64,
            related_symbol=stocks[0].name if stocks else theme.name,
            content=f"{theme.name}涨停池匹配 {len(stocks)} 家，短线重点看核心封单和跟风扩散。",
        ),
        ResearcherOpinion(
            id=f"{theme.id}-op-aping",
            researcher_id="aping",
            researcher_name="基本面分析·阿平",
            avatar_initial="平",
            avatar_color="brand",
            stance="neutral",
            confidence_pct=72,
            related_symbol=theme.name,
            content="题材需要后续产业或政策数据验证，单日涨停只作为情绪信号。",
        ),
        ResearcherOpinion(
            id=f"{theme.id}-op-azhi",
            researcher_id="azhi",
            researcher_name="风控·阿智",
            avatar_initial="智",
            avatar_color="gold",
            stance="watch" if cautious else "neutral",
            confidence_pct=68,
            related_symbol=stocks[0].name if stocks else theme.name,
            content="若核心标的炸板或封单衰减，说明一致预期开始松动，需要降低追高权重。",
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
        researcher_count=8,
        they_say=_build_they_say_from_market(snapshot),
        event_chain=_event_chain_from_market(enriched, snapshot),
        expectation_gaps=_expectation_gaps_from_market(enriched, snapshot),
        market_story=_market_story_from_market(enriched, snapshot),
        hidden_logic=_hidden_logic_from_market(enriched, snapshot),
        anchor_recommendations=_anchor_recommendations_from_market(enriched, snapshot),
        scenarios=_scenarios_from_market(enriched, snapshot),
        opinions=_opinions_from_market(enriched, snapshot),
        consensus=_consensus_from_market(enriched, snapshot),
    )


# ---------- 半导体题材完整内容（8 大模块） ----------
def _semiconductor_detail() -> ThemeDetail:
    return ThemeDetail(
        id="semiconductor",
        name="半导体产业链",
        status="today_hot",
        limit_up_count=13,
        researcher_count=8,
        they_say=build_they_say(),
        event_chain=EventDrivenChain(
            past_events=[
                PastEvent(
                    id="evt-1",
                    title="国常会研究部署「人工智能+行动」实施方案",
                    description="明确 AI 与制造业、医疗、教育深度融合方向，自主可控半导体设备/材料受益最直接。",
                    impact="high",
                    category="policy",
                    occurred_at="已过去 · 5/20",
                    source="央视新闻",
                ),
                PastEvent(
                    id="evt-2",
                    title="中信证券：半导体设备国产化率有望从 35% 提升至 60%",
                    description="2,000 亿增量空间，大基金三期 3,440 亿持续加码。",
                    impact="high",
                    category="industry",
                    occurred_at="已过去 · 5/21",
                    source="中信证券",
                ),
                PastEvent(
                    id="evt-3",
                    title="中微公司分红派现 11.2 亿元，每 10 股派 18 元",
                    description="分红超预期，传递订单饱满 / 现金流充足信号。",
                    impact="medium",
                    category="company",
                    occurred_at="今天 · 5/22",
                    source="公司公告",
                ),
            ],
            future_expectations=[
                FutureExpectation(
                    id="fut-1",
                    kind="catalyst",
                    title="华为 Mate70 发布会 · 自研 Kirin 9100 揭幕",
                    description=(
                        "预期差：市场已部分定价，但 GPU / NPU 算力指标若超预期，"
                        "可二次催化 GPU 国产替代题材。"
                    ),
                    when="明天 · 5/23",
                ),
                FutureExpectation(
                    id="fut-2",
                    kind="risk",
                    title="高位回吐 + 解禁压力",
                    description=(
                        "中芯国际 PE 208 倍处历史 95% 分位，5/26 中芯国际解禁市值 412 亿，谨慎追高。"
                    ),
                    when="5 天内",
                ),
            ],
            core_target_groups=[
                CoreTargetGroup(
                    role="sentiment_core",
                    label="情绪核心",
                    items=[
                        CoreTarget(symbol="300641", name="正丹股份", metric="7 板", note="题材龙头"),
                        CoreTarget(symbol="300069", name="金利华电", metric="3 板", note="收购中科西光"),
                    ],
                ),
                CoreTargetGroup(
                    role="logic_core",
                    label="逻辑核心",
                    items=[
                        CoreTarget(symbol="688012", name="中微公司", metric="+8.2%", note="设备龙头·分红超预期"),
                        CoreTarget(symbol="002371", name="北方华创", metric="+5.1%", note="国产化最大受益"),
                    ],
                ),
                CoreTargetGroup(
                    role="trend_anchor",
                    label="趋势中军",
                    items=[
                        CoreTarget(symbol="688256", name="寒武纪", metric="+6.4%", note="主力净流入 2.1 亿"),
                        CoreTarget(symbol="002463", name="沪电股份", metric="+4.7%", note="PCB 联动"),
                    ],
                ),
            ],
        ),
        expectation_gaps=[
            ExpectationGap(
                id="gap-1",
                direction="undervalued",
                target_label="半导体设备",
                title="国产替代加速度远超机构 35% 预期",
                magnitude_pct=45.2,
                reasoning=(
                    "大基金三期 + 政策窗口 + 美方限制升级三力叠加，"
                    "国产化率到 60% 时间从 3 年压缩到 18 月。"
                ),
            ),
            ExpectationGap(
                id="gap-2",
                direction="overvalued",
                target_label="存储龙头",
                title="兆易创新 PE 208 倍透支 2-3 年业绩",
                magnitude_pct=-32.8,
                reasoning=(
                    "研报「高位唱多」明显有出货嫌疑，"
                    "PE 已突破 5 年估值 95% 分位线，赔率极差。"
                ),
            ),
        ],
        market_story=MarketStory(
            today=[
                MarketStorySegment(
                    time_range="09:30 - 10:00",
                    headline="高开 · 主力借助美股映射拉升半导体",
                    narrative=(
                        "隔夜美股科技股领涨，电子板块主力净流入 254.91 亿断层第一。"
                        "寒武纪、中微 30 秒涨停首板封死，传染效应触发情绪共振。"
                    ),
                ),
                MarketStorySegment(
                    time_range="10:00 - 11:30",
                    headline="扩散 · PCB / 液冷 / MLCC 接力",
                    narrative=(
                        "摩根士丹利 Rubin 价值量测算引爆 PCB 板块，沪电股份带头 26 只涨停。"
                        "资金虹吸效应明显，二线开始炸板抢筹。"
                    ),
                ),
                MarketStorySegment(
                    time_range="13:00 - 15:00",
                    headline="分歧 · 高位回吐 + 低位低吸",
                    narrative=(
                        "下午开盘高位股出现明显获利回吐，但资金向低位补涨股切换，"
                        "金利华电、四环生物等中位股扛旗封板，封板率维持 82.73%。"
                    ),
                ),
            ],
            yesterday=[
                MarketStorySegment(
                    time_range="09:30 - 11:30",
                    headline="震荡蓄势 · 大盘缩量等待方向",
                    narrative="半导体板块整体震荡，沪电股份午前突破带动情绪修复，但量能未跟上。",
                ),
                MarketStorySegment(
                    time_range="13:00 - 15:00",
                    headline="尾盘异动 · 设备股集体走强",
                    narrative="尾盘 14:30 后中微公司、北方华创放量拉升，提前抢跑次日政策预期。",
                ),
            ],
        ),
        hidden_logic=[
            HiddenLogicItem(
                id="hl-1",
                title="① 风电运维 ⟶ 半导体测试设备",
                description=(
                    "中际旭创 + 国电南瑞设备订单异动指向风电运维数字化升级，"
                    "背后核心是半导体测试模组的产能扩张。"
                ),
                tags=["中际旭创", "国电南瑞", "半导体测试"],
            ),
            HiddenLogicItem(
                id="hl-2",
                title="② 创新药出海退税 ⟶ CRO/CDMO 产能利用率",
                description=(
                    "10 月退税细则落地 → 药明康德订单回流 → CRO 产能利用率 Q3 反弹 "
                    "→ 半导体 IC 设计转单效应。"
                ),
                tags=["药明康德", "凯莱英"],
            ),
            HiddenLogicItem(
                id="hl-3",
                title="③ 算力租赁价格指数 ⟶ AI 应用复苏",
                description="算力价格周环比连续 4 周下行，意味着推理侧需求释放将提速。",
                tags=["寒武纪", "算力租赁"],
            ),
        ],
        anchor_recommendations=[
            AnchorRecommendItem(
                horizon="today",
                label="最具爆发潜力",
                title="半导体设备国产替代",
                description=(
                    "大基金三期 3,440 亿 + 政策催化 + 美方限制升级三力叠加，国产化率提速"
                ),
                related_symbols=["中微公司", "北方华创"],
            ),
            AnchorRecommendItem(
                horizon="this_week",
                label="本周主线",
                title="PCB 价值重估",
                description="英伟达 Rubin 架构 PCB 价值量激增 233% 引爆估值重估",
                related_symbols=["沪电股份", "胜宏科技"],
            ),
        ],
        scenarios=[
            Scenario(
                kind="optimistic",
                label="乐观 · 45%",
                probability=0.45,
                title="华为发布会超预期 · 题材二次发酵",
                strategy="低吸今日炸板 / 一进二预期；目标价位 +6%",
                key_observation="开盘 30 分钟 PCB 板块成交额 / 资金流入",
            ),
            Scenario(
                kind="neutral",
                label="震荡 · 40%",
                probability=0.40,
                title="分化加剧 · 高低切换",
                strategy="高位减持 / 低位轮动；半仓应对",
                key_observation="10 点前一二线分化幅度",
            ),
            Scenario(
                kind="pessimistic",
                label="悲观 · 15%",
                probability=0.15,
                title="解禁砸盘 · 题材冷却",
                strategy="清仓观望 / 转防御板块（银行、公用事业）",
                key_observation="中芯国际盘前北向方向、午后情绪指数",
            ),
        ],
        opinions=[
            ResearcherOpinion(
                id="op-1",
                researcher_id="afa",
                researcher_name="情绪超短·阿发",
                avatar_initial="发",
                avatar_color="up",
                stance="bullish",
                confidence_pct=92,
                related_symbol="寒武纪",
                content="PCB 板块虹吸效应叠加华为发布会催化，明日大概率二次发酵，重点把握低吸机会。",
            ),
            ResearcherOpinion(
                id="op-2",
                researcher_id="aping",
                researcher_name="基本面分析·阿平",
                avatar_initial="平",
                avatar_color="brand",
                stance="bullish",
                confidence_pct=85,
                related_symbol="中微公司",
                content=(
                    "分红比例超预期反映管理层信心；设备国产化率提速逻辑成立，"
                    "但短期估值偏高，等回调到 ¥175。"
                ),
            ),
            ResearcherOpinion(
                id="op-3",
                researcher_id="along",
                researcher_name="技术派·阿龙",
                avatar_initial="龙",
                avatar_color="down",
                stance="bearish",
                confidence_pct=78,
                related_symbol="兆易创新",
                content="K 线已经走出明显的「出货顶背离」，估值透支 2-3 年业绩，建议高位减持。",
            ),
            ResearcherOpinion(
                id="op-4",
                researcher_id="taotao",
                researcher_name="桃桃高·宏观",
                avatar_initial="桃",
                avatar_color="gold",
                stance="neutral",
                confidence_pct=65,
                related_symbol="半导体",
                content="全球半导体周期复苏的 β 还没确认，国内政策 α 明确但难以独立支撑过高估值。",
            ),
            ResearcherOpinion(
                id="op-5",
                researcher_id="ahai",
                researcher_name="资金流·阿海",
                avatar_initial="海",
                avatar_color="up",
                stance="bullish",
                confidence_pct=88,
                related_symbol="沪电股份",
                content="北向连续 3 日净流入 PCB 板块超 12 亿，主力资金加仓显著。",
            ),
            ResearcherOpinion(
                id="op-6",
                researcher_id="awen",
                researcher_name="政策研究·阿文",
                avatar_initial="文",
                avatar_color="brand",
                stance="bullish",
                confidence_pct=82,
                related_symbol="北方华创",
                content="大基金三期落地节奏快于市场预期，设备龙头业绩弹性最大。",
            ),
            ResearcherOpinion(
                id="op-7",
                researcher_id="azhi",
                researcher_name="风控·阿智",
                avatar_initial="智",
                avatar_color="gold",
                stance="watch",
                confidence_pct=60,
                related_symbol="中芯国际",
                content="5/26 解禁市值 412 亿压力较大，建议观望 1-2 个交易日再确认方向。",
            ),
            ResearcherOpinion(
                id="op-8",
                researcher_id="aji",
                researcher_name="量化·阿吉",
                avatar_initial="吉",
                avatar_color="up",
                stance="bullish",
                confidence_pct=76,
                related_symbol="正丹股份",
                content="动量因子 + 情绪因子双高位，趋势仍未破，按高位龙头节奏短打。",
            ),
        ],
        consensus=ConsensusBreakdown(
            bullish=6,
            neutral=1,
            bearish=1,
            watch=1,
            summary="强共识 · 主流方向高度一致",
        ),
    )


def _generic_detail(theme: ThemeListItem) -> ThemeDetail:
    """对其他题材返回一个简化但完整的 mock，便于点击任意题材也能渲染整页。"""
    return ThemeDetail(
        id=theme.id,
        name=theme.name,
        status=theme.status,
        limit_up_count=theme.limit_up_count,
        researcher_count=5,
        they_say=TheySayBoard(
            generated_at=datetime.now(timezone.utc),
            sentiment_direction="neutral",
            sentiment_label="中性 · 分歧",
            bullish_count=3,
            neutral_count=2,
            bearish_count=2,
            confidence=5.6,
            cycle="观察期",
            cycle_note="尚未出现明确主线，等待催化",
            summary=f"{theme.name} 当前共识分散，建议关注后续政策与龙头动向。",
        ),
        event_chain=EventDrivenChain(
            past_events=[
                PastEvent(
                    id=f"{theme.id}-e1",
                    title=f"{theme.name} · 行业最新政策吹风",
                    description="近期政策表述偏积极，市场期待落地细则。",
                    impact="medium",
                    category="policy",
                    occurred_at="本周",
                ),
            ],
            future_expectations=[
                FutureExpectation(
                    id=f"{theme.id}-f1",
                    kind="catalyst",
                    title=f"{theme.name} 行业大会即将召开",
                    description="可能释放需求侧增量信号。",
                    when="下周",
                ),
            ],
            core_target_groups=[
                CoreTargetGroup(
                    role="logic_core",
                    label="逻辑核心",
                    items=[
                        CoreTarget(symbol="---", name=f"{theme.name}龙头", metric="+3.5%", note="跟踪重点"),
                    ],
                ),
            ],
        ),
        expectation_gaps=[
            ExpectationGap(
                id=f"{theme.id}-gap",
                direction="undervalued",
                target_label=theme.name,
                title="二线标的存在补涨预期差",
                magnitude_pct=12.5,
                reasoning="一线龙头已被定价，资金可能切换至估值更低的二线。",
            ),
        ],
        market_story=MarketStory(
            today=[
                MarketStorySegment(
                    time_range="09:30 - 11:30",
                    headline="观望 · 缺乏明确主线",
                    narrative=f"{theme.name} 全天震荡，成交相比昨日略有萎缩。",
                ),
            ],
            yesterday=[],
        ),
        hidden_logic=[
            HiddenLogicItem(
                id=f"{theme.id}-hl",
                title=f"{theme.name} ⟶ 关联消费侧",
                description="二阶传导仍待观察。",
                tags=[theme.name],
            ),
        ],
        anchor_recommendations=[
            AnchorRecommendItem(
                horizon="this_week",
                label="本周观察",
                title=f"{theme.name} 主线",
                description="待催化事件落地后再确认方向。",
                related_symbols=[],
            ),
        ],
        scenarios=[
            Scenario(kind="optimistic", label="乐观 · 30%", probability=0.30, title="催化兑现 · 主线确立", strategy="顺势加仓", key_observation="龙头封板时间"),
            Scenario(kind="neutral", label="震荡 · 50%", probability=0.50, title="维持震荡", strategy="低吸高抛", key_observation="量能变化"),
            Scenario(kind="pessimistic", label="悲观 · 20%", probability=0.20, title="资金流出", strategy="减仓观望", key_observation="北向方向"),
        ],
        opinions=[
            ResearcherOpinion(
                id=f"{theme.id}-op1",
                researcher_id="aping",
                researcher_name="基本面分析·阿平",
                avatar_initial="平",
                avatar_color="brand",
                stance="neutral",
                confidence_pct=60,
                related_symbol=theme.name,
                content=f"{theme.name} 基本面尚未出现拐点信号，保持中性。",
            ),
        ],
        consensus=ConsensusBreakdown(bullish=3, neutral=2, bearish=2, watch=0, summary="分歧 · 等待主线"),
    )


THEME_DETAILS: dict[str, ThemeDetail] = {"semiconductor": _semiconductor_detail()}


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
                if snapshot.pool or snapshot.boards or snapshot.news:
                    return _detail_from_market(theme, snapshot)
                return THEME_DETAILS.get(theme_id) or _generic_detail(theme)
        return None

    def they_say(self) -> TheySayBoard:
        snapshot = _load_market_snapshot()
        if snapshot.pool or snapshot.boards:
            return _build_they_say_from_market(snapshot)
        return build_they_say(snapshot.generated_at)

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
