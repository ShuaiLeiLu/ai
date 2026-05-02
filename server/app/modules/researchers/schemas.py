from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import SchemaModel

WorkbenchRankSortBy = Literal["today", "month"]
ResearcherVisibility = Literal["draft", "private", "public"]
ResearcherPublishStatus = Literal["draft", "published", "unpublished"]


class ResearcherSummary(SchemaModel):
    researcher_id: str
    name: str
    title: str
    style: str
    status: str
    today_pnl: float
    win_rate_30d: float
    level: str


class ResearcherDetail(ResearcherSummary):
    avatar_url: str | None = None
    description: str
    prompt: str
    visibility: ResearcherVisibility = "draft"
    published_version: str | None = None
    skills: list[str] = Field(default_factory=list)
    knowledge_bases: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    self_drive_tasks: list[str] = Field(default_factory=list, max_length=10)
    # 策略配置（JSONB）—— 每个研究员的专属交易策略参数
    strategy_config: dict | None = None
    created_at: datetime
    updated_at: datetime


class ResearcherCreateRequest(SchemaModel):
    name: str = Field(min_length=1, max_length=32)
    title: str = Field(default="自定义研究员", max_length=64)
    style: str = Field(default="均衡", max_length=64)
    description: str = Field(default="", max_length=1000)
    prompt: str = Field(default="", max_length=10000)
    visibility: ResearcherVisibility = "draft"
    skills: list[str] = Field(default_factory=list, max_length=50)
    knowledge_bases: list[str] = Field(default_factory=list, max_length=50)
    mcp_servers: list[str] = Field(default_factory=list, max_length=50)
    self_drive_tasks: list[str] = Field(default_factory=list, max_length=10)
    strategy_config: dict | None = None


class ResearcherUpdateRequest(SchemaModel):
    title: str | None = Field(default=None, max_length=64)
    style: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=1000)
    prompt: str | None = Field(default=None, max_length=10000)
    visibility: ResearcherVisibility | None = None
    skills: list[str] | None = Field(default=None, max_length=50)
    knowledge_bases: list[str] | None = Field(default=None, max_length=50)
    mcp_servers: list[str] | None = Field(default=None, max_length=50)
    self_drive_tasks: list[str] | None = Field(default=None, max_length=10)
    strategy_config: dict | None = None


class WorkbenchHiredResearcher(SchemaModel):
    """工作台「已雇佣研究员」卡片。"""

    researcher_id: str
    avatar_url: str | None = None
    name: str
    summary: str
    status: str
    tags: list[str] = Field(default_factory=list)
    today_yield: float | None = None
    today_yield_rate: float | None = None
    month_yield_rate: float | None = None
    total_asset: float | None = None
    win_rate_30d: float | None = None
    has_trading_account: bool = False
    level: str


class WorkbenchHotDocument(SchemaModel):
    """工作台热门文档条目。"""

    id: str
    title: str
    summary: str
    researcher_name: str
    create_time: datetime
    view_count: int | None = None
    comment_count: int | None = None
    metrics_ready: bool = False


class WorkbenchPublicRankItem(SchemaModel):
    """公开研究员收益榜条目。"""

    researcher_id: str
    name: str
    total_asset: float
    today_yield_rate: float
    month_yield_rate: float
    risk_note: str


class WorkbenchQuickAction(SchemaModel):
    """首屏快捷动作，便于前端后续扩展为按钮/入口卡片。"""

    action_key: str
    title: str
    description: str


class WorkbenchOverview(SchemaModel):
    """工作台首屏聚合结果。

    partial_failures 用于表达局部数据源失败且整体仍可用的语义。
    """

    hired: list[WorkbenchHiredResearcher] = Field(default_factory=list)
    hot_documents: list[WorkbenchHotDocument] = Field(default_factory=list)
    rankings: list[WorkbenchPublicRankItem] = Field(default_factory=list)
    quick_actions: list[WorkbenchQuickAction] = Field(default_factory=list)
    risk_disclaimer: str
    partial_failures: list[str] = Field(default_factory=list)


class ResearcherMarketCard(SchemaModel):
    """人才市场卡片。"""

    id: str
    name: str
    avatar: str | None = None
    introduction: str
    level: str
    hire_count: int = 0
    version: str
    tags: list[str] = Field(default_factory=list)
    template_visible: bool = False
    is_hired: bool = False


class ResearcherMarketDetail(ResearcherMarketCard):
    """人才市场详情，补充模板可见与简历信息。"""

    resume: str
    prompt: str


class ResearcherMineItem(SchemaModel):
    """我的研究员列表项，包含发布状态信息。"""

    id: str
    name: str
    avatar: str | None = None
    introduction: str
    level: str
    visibility: ResearcherVisibility
    published_version: str | None = None
    publish_status: ResearcherPublishStatus = "draft"
    version: str
    updated_at: datetime


class ResearcherPublishRecord(SchemaModel):
    """发布记录（简化）。"""

    version: str
    publish_time: datetime
    status: ResearcherPublishStatus


class ResearcherOptionItem(SchemaModel):
    id: str
    name: str


class ResearcherTestChatRequest(SchemaModel):
    question: str = Field(min_length=1, max_length=2000)


class ResearcherTestChatResponse(SchemaModel):
    researcher_id: str
    question: str
    answer: str
    version_used: str
    reply_time: datetime
