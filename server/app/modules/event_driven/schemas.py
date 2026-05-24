"""
题材掘金 · 事件驱动模块 Pydantic 模型。

对齐设计稿 5.5 / 5.5B 八大子模块：
  ① 它们说 AI 共识看板
  ② 事件驱动链（已发生 / 未来预期 / 核心标的）
  ③ 预期差雷达
  ④ 盘口故事
  ⑤ 暗线逻辑
  ⑥ 主心骨推荐
  ⑦ 推演场景
  ⑧ 观点汇集
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.common import SchemaModel

# ===== 公共枚举 =====
ThemeStatus = Literal["today_hot", "yesterday_hot", "waiting", "lurking"]
SentimentDirection = Literal["bullish", "bearish", "neutral"]
ImpactLevel = Literal["high", "medium", "low"]
EventCategory = Literal["policy", "theme", "sentiment", "industry", "company", "macro", "other"]
RoleGroup = Literal["sentiment_core", "logic_core", "trend_anchor"]
DeviationDirection = Literal["undervalued", "overvalued"]
OpinionStance = Literal["bullish", "bearish", "neutral", "watch"]
ScenarioKind = Literal["optimistic", "neutral", "pessimistic"]
RecommendHorizon = Literal["today", "this_week"]


# ===== 访问状态 =====
class AccessStatus(SchemaModel):
    vip: bool
    unlocked_today: bool
    battery_balance: int
    unlock_cost: int = 200


class UnlockResult(SchemaModel):
    success: bool
    battery_balance: int
    unlocked_until: datetime


# ===== 题材列表 =====
class ThemeListItem(SchemaModel):
    id: str
    rank: int
    name: str
    status: ThemeStatus
    limit_up_count: int
    event_count: int


# ===== 它们说看板 =====
class TheySayBoard(SchemaModel):
    generated_at: datetime
    sentiment_direction: SentimentDirection
    sentiment_label: str  # 例如"偏多 · 强共识"
    bullish_count: int
    neutral_count: int
    bearish_count: int
    confidence: float  # 0-10
    cycle: str  # 例如"发酵期"
    cycle_note: str
    summary: str


# ===== 事件驱动链 =====
class PastEvent(SchemaModel):
    id: str
    title: str
    description: str
    impact: ImpactLevel
    category: EventCategory
    occurred_at: str  # "今天 · 5/22" / "已过去 · 5/20"
    source: str | None = None


class FutureExpectation(SchemaModel):
    id: str
    kind: Literal["catalyst", "risk"]  # 利好催化点 / 风险提示
    title: str
    description: str
    when: str  # 例如"明天 · 5/23" / "5 天内"


class CoreTarget(SchemaModel):
    symbol: str
    name: str
    metric: str  # 例如"7 板" / "+8.2%"
    note: str


class CoreTargetGroup(SchemaModel):
    role: RoleGroup
    label: str  # 例如"情绪核心 / 逻辑核心 / 趋势中军"
    items: list[CoreTarget]


class EventDrivenChain(SchemaModel):
    past_events: list[PastEvent]
    future_expectations: list[FutureExpectation]
    core_target_groups: list[CoreTargetGroup]


# ===== 预期差雷达 =====
class ExpectationGap(SchemaModel):
    id: str
    direction: DeviationDirection
    target_label: str  # 例如"半导体设备"
    title: str
    magnitude_pct: float  # 正负百分比
    reasoning: str


# ===== 盘口故事 =====
class MarketStorySegment(SchemaModel):
    time_range: str
    headline: str
    narrative: str


class MarketStory(SchemaModel):
    today: list[MarketStorySegment]
    yesterday: list[MarketStorySegment]


# ===== 暗线逻辑 =====
class HiddenLogicItem(SchemaModel):
    id: str
    title: str  # 例如"风电运维 ⟶ 半导体测试设备"
    description: str
    tags: list[str]


# ===== 主心骨推荐 =====
class AnchorRecommendItem(SchemaModel):
    horizon: RecommendHorizon
    label: str  # 例如"最具爆发潜力"
    title: str
    description: str
    related_symbols: list[str]


# ===== 推演场景 =====
class Scenario(SchemaModel):
    kind: ScenarioKind
    label: str  # 例如"乐观 · 45%"
    probability: float
    title: str
    strategy: str
    key_observation: str


# ===== 观点汇集 =====
class ResearcherOpinion(SchemaModel):
    id: str
    researcher_id: str
    researcher_name: str
    avatar_initial: str
    avatar_color: str
    stance: OpinionStance
    confidence_pct: float
    related_symbol: str | None = None
    content: str


class ConsensusBreakdown(SchemaModel):
    bullish: int
    neutral: int
    bearish: int
    watch: int = 0
    summary: str  # 例如"强共识 · 主流方向高度一致"


# ===== 题材详情聚合 =====
class ThemeDetail(SchemaModel):
    id: str
    name: str
    status: ThemeStatus
    limit_up_count: int
    researcher_count: int
    they_say: TheySayBoard
    event_chain: EventDrivenChain
    expectation_gaps: list[ExpectationGap]
    market_story: MarketStory
    hidden_logic: list[HiddenLogicItem]
    anchor_recommendations: list[AnchorRecommendItem]
    scenarios: list[Scenario]
    opinions: list[ResearcherOpinion]
    consensus: ConsensusBreakdown
