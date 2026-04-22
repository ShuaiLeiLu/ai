"""
研究员领域服务

双模式运行：
  1. 数据库模式（async 方法）：通过 Repository 操作 PostgreSQL
  2. 内存 mock 模式（sync 方法）：数据库未就绪时的降级方案

包含功能：
  - 研究员 CRUD（创建/编辑/复制/发布/下架）
  - 市场列表与搜索
  - 雇佣/解雇管理
  - 工作台数据聚合（已雇佣、热门文档、公开排名）
  - 测试对话（后续接入 LLM）
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Callable
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.researcher import Researcher as ResearcherModel
from app.models.researcher import ResearcherHire as HireModel
from app.repositories.researcher_repo import ResearcherHireRepository, ResearcherRepository

from app.modules.researchers.schemas import (
    ResearcherCreateRequest,
    ResearcherDetail,
    ResearcherMarketCard,
    ResearcherMarketDetail,
    ResearcherMineItem,
    ResearcherOptionItem,
    ResearcherPublishRecord,
    ResearcherSummary,
    ResearcherTestChatResponse,
    ResearcherUpdateRequest,
    WorkbenchHiredResearcher,
    WorkbenchHotDocument,
    WorkbenchOverview,
    WorkbenchPublicRankItem,
    WorkbenchQuickAction,
    WorkbenchRankSortBy,
)


class ResearcherService:
    """研究员领域服务。

    当前为内存实现，后续会迁移到 repository + PostgreSQL 持久化。
    """

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
        # ── 研究员详情数据（mock），保证前端页面可直接联调 ──
        self._researchers: dict[str, ResearcherDetail] = {
            # ① 市场趋势-找买
            "r_trend": ResearcherDetail(
                researcher_id="r_trend",
                name="市场趋势-找买",
                title="中线择时专家",
                style="技术分析+事件驱动",
                status="active",
                today_pnl=2270.0,
                win_rate_30d=0.63,
                level="LV.2",
                avatar_url=None,
                description="擅长热点轮动与情绪拐点判断，偏好高流动性标的。通过技术面与事件催化共振，在中线维度给出结构化交易计划。",
                prompt=(
                    "你是一名名叫「市场趋势-找买」的A股中线择时研究员。\n"
                    "核心能力：趋势追踪、事件驱动择时、热点轮动判断。\n"
                    "你应当关注：行业强弱变化、龙头分歧转一致、成交量能变化。\n"
                    "输出要求：每次回复需包含【市场环境研判】【行业方向】【个股建议】三部分，"
                    "明确标注风险提示。\n"
                ),
                visibility="public",
                published_version="v1",
                skills=["skill_event_drive", "skill_tech_analysis"],
                knowledge_bases=["kb_market_daily", "kb_chip_data"],
                mcp_servers=["mcp_financial_news"],
                self_drive_tasks=["盘前检查行业强弱", "盘中监控龙头分歧转一致", "收盘后统计板块涨跌变化"],
                created_at=now,
                updated_at=now,
            ),
            # ② 量化稳健者
            "r_quant": ResearcherDetail(
                researcher_id="r_quant",
                name="量化稳健者",
                title="多因子量化专家",
                style="量化因子+风控体系",
                status="active",
                today_pnl=845.0,
                win_rate_30d=0.68,
                level="LV.3",
                avatar_url=None,
                description="基于多因子选股与严格风控体系，追求低回撤下的稳定阿尔法收益。覆盖价值、成长、动量、质量等因子维度。",
                prompt=(
                    "你是一名名叫「量化稳健者」的A股量化研究员。\n"
                    "核心能力：多因子选股、风险预算管理、组合优化。\n"
                    "因子体系：价值（PB/PE/PEG）、成长（营收增速/利润增速）、"
                    "动量（20日/60日涨幅）、质量（ROE/毛利率）、低波（波动率/换手率）。\n"
                    "风控规则：单票不超过总仓位15%，行业不超过30%，最大回撤止损8%。\n"
                    "输出要求：每次回复需包含【因子信号】【持仓建议】【风险评估】三部分，"
                    "给出具体的仓位配比建议。\n"
                ),
                visibility="public",
                published_version="v2",
                skills=["skill_quant_factor", "skill_risk_management"],
                knowledge_bases=["kb_market_daily", "kb_factor_data"],
                mcp_servers=["mcp_financial_news", "mcp_fund_flow"],
                self_drive_tasks=["每日因子打分并输出TOP20候选池", "监控组合最大回撤", "周度调仓建议"],
                created_at=now,
                updated_at=now,
            ),
            # ③ 小米研究员-雷锋
            "r_smallcap": ResearcherDetail(
                researcher_id="r_smallcap",
                name="小米研究员-雷锋",
                title="小盘成长猎手",
                style="小盘股+成长弹性",
                status="active",
                today_pnl=1350.0,
                win_rate_30d=0.58,
                level="LV.2",
                avatar_url=None,
                description="深耕小盘成长股，擅长发掘早期高弹性标的。关注流通市值偏小、业绩拐点明确的个股，追求超额收益。",
                prompt=(
                    "你是一名名叫「小米研究员-雷锋」的A股小盘成长研究员。\n"
                    "核心能力：小盘股筛选、业绩拐点判断、成长弹性评估。\n"
                    "选股偏好：流通市值20-80亿，营收增速>20%，净利润转正或大幅改善。\n"
                    "风控规则：单票仓位上限10%，止损线-8%，连续涨停后减仓锁利。\n"
                    "输出要求：每次回复需包含【个股亮点】【估值水平】【催化事件】【风险提示】，"
                    "对标的给出明确的买入/持有/卖出建议。\n"
                ),
                visibility="public",
                published_version="v1",
                skills=["skill_growth_screening", "skill_tech_analysis"],
                knowledge_bases=["kb_market_daily", "kb_smallcap_data"],
                mcp_servers=["mcp_financial_news"],
                self_drive_tasks=["每日筛选小盘成长股候选池", "跟踪持仓个股业绩预告", "监控小盘指数走势"],
                created_at=now,
                updated_at=now,
            ),
            # ④ 小市值轮动研究员（基于用户提供的聚宽策略）
            "r_smallcap_rotate": ResearcherDetail(
                researcher_id="r_smallcap_rotate",
                name="小市值轮动",
                title="A股小市值轮动策略专家",
                style="因子轮动+小市值+量化执行",
                status="active",
                today_pnl=1680.0,
                win_rate_30d=0.61,
                level="LV.2",
                avatar_url=None,
                description=(
                    "专注A股全市场小市值轮动策略。通过SG（5年营收增长率）、MS（复合成长因子）、"
                    "PEG三大因子选股，取交集后按流通市值升序排列，持仓10只，每日调仓。"
                    "内置10%硬止损、涨停打开自动卖出、近20日涨停股黑名单等风控规则。"
                ),
                prompt=(
                    "你是一名名叫「小市值轮动」的A股量化策略研究员，专注小市值股票的因子轮动策略。\n\n"
                    "## 策略核心逻辑\n\n"
                    "### 选股体系（三因子融合）\n"
                    "1. **SG因子**：5年营业收入增长率（sales_growth）前10%，过滤EPS≤0，按流通市值升序\n"
                    "2. **MS因子（复合成长因子）**：\n"
                    "   - 营收增长率权重10% + 利润总额增长率权重35% + 净利润增长率权重15% + 盈利增长率权重40%\n"
                    "   - 综合评分前10%，过滤EPS≤0，按流通市值升序\n"
                    "3. **PEG因子**：PEG前20% → 换手率波动率前50%，按流通市值升序\n"
                    "4. **合并**：三池取并集 → 按流通市值升序 → 取前10只\n\n"
                    "### 过滤规则\n"
                    "- 排除：ST/*ST/退市股、科创板(688)、次新股(上市<375天)、停牌股、涨停股、跌停股\n"
                    "- 黑名单：近20个交易日内持仓过且期间涨停过的股票不再买入\n\n"
                    "### 风控规则\n"
                    "- **止损线**：持仓个股亏损达-10%立即卖出\n"
                    "- **涨停管理**：昨日涨停股在14:00检查，若涨停打开则立即卖出，否则继续持有\n"
                    "- **调仓频率**：每个交易日9:30执行调仓\n"
                    "- **持仓数量**：目标持仓10只，等权分配资金\n\n"
                    "### 交易成本\n"
                    "- 买入佣金万三，卖出佣金万三 + 印花税千一，最低5元\n\n"
                    "## 输出要求\n"
                    "每次回复需包含以下结构：\n"
                    "1. **今日选股池**：列出SG/MS/PEG三个子池及合并后的最终候选\n"
                    "2. **调仓信号**：需卖出的持仓（及原因）、需买入的标的（及入选因子）\n"
                    "3. **风控状态**：当前止损监控、涨停持仓状态、黑名单股票\n"
                    "4. **策略指标**：最高连板数、封板率、持仓盈亏分布\n"
                    "5. **风险提示**：明确标注小市值策略的流动性风险和极端回撤风险\n"
                ),
                visibility="public",
                published_version="v1",
                skills=["skill_smallcap_rotation", "skill_quant_factor", "skill_risk_management"],
                knowledge_bases=["kb_market_daily", "kb_factor_data", "kb_smallcap_data"],
                mcp_servers=["mcp_financial_news", "mcp_fund_flow"],
                self_drive_tasks=[
                    "9:05 执行选股（SG+MS+PEG三因子合并）并输出候选池",
                    "9:30 执行每日调仓（卖出不在目标池 + 买入新目标）",
                    "14:00 检查昨日涨停持仓是否打开，打开则卖出",
                    "14:30 检查持仓止损（亏损超-10%自动卖出）",
                    "15:01 输出收盘选股摘要与信号推送",
                    "15:10 输出每日持仓明细报告",
                ],
                created_at=now,
                updated_at=now,
            ),
            # ⑤ 情绪超短阿发（保留）
            "r_sentiment": ResearcherDetail(
                researcher_id="r_sentiment",
                name="情绪超短-阿发",
                title="短线博弈专家",
                style="盘口情绪+资金流",
                status="idle",
                today_pnl=-576.0,
                win_rate_30d=0.54,
                level="LV.1",
                avatar_url=None,
                description="聚焦超短情绪周期，关注竞价与换手结构。",
                prompt="你是一名超短情绪研究员，优先输出风险与仓位建议。",
                visibility="private",
                published_version=None,
                skills=["skill_short_term_sentiment"],
                knowledge_bases=["kb_tick_data"],
                mcp_servers=["mcp_l2_quote"],
                self_drive_tasks=["收盘后复盘涨停梯队"],
                created_at=now,
                updated_at=now,
            ),
        }

        self._market_meta: dict[str, dict[str, object]] = {
            "r_trend": {
                "hire_count": 238,
                "version": "v1",
                "tags": ["技术面", "事件驱动", "中线"],
                "template_visible": True,
                "resume": "8年A股交易与研究经验，主攻趋势与催化共振场景。",
            },
            "r_quant": {
                "hire_count": 185,
                "version": "v2",
                "tags": ["量化", "多因子", "低回撤"],
                "template_visible": True,
                "resume": "量化策略开发经验丰富，擅长多因子模型与组合优化，追求稳定阿尔法。",
            },
            "r_smallcap": {
                "hire_count": 142,
                "version": "v1",
                "tags": ["小盘股", "成长", "弹性"],
                "template_visible": True,
                "resume": "深耕小盘成长股赛道，关注业绩拐点与市值弹性，擅长早期标的发掘。",
            },
            "r_smallcap_rotate": {
                "hire_count": 67,
                "version": "v1",
                "tags": ["小市值", "因子轮动", "量化", "每日调仓"],
                "template_visible": True,
                "resume": (
                    "基于聚宽平台实盘验证的小市值轮动策略研究员。"
                    "运用SG/MS/PEG三因子选股体系，每日调仓，内置止损与涨停管理，"
                    "适合追求超额收益且能承受一定回撤的投资者。"
                ),
            },
            "r_sentiment": {
                "hire_count": 96,
                "version": "v0",
                "tags": ["情绪周期", "超短", "风控"],
                "template_visible": False,
                "resume": "擅长情绪博弈模型，关注盘口行为与资金切换。",
            },
        }
        # 模拟当前登录用户的“我的研究员”与“已雇佣研究员”。
        self._mine_researcher_ids: set[str] = {
            "r_trend", "r_quant", "r_smallcap", "r_smallcap_rotate", "r_sentiment",
        }
        self._hired_researcher_ids: set[str] = {
            "r_trend", "r_quant", "r_smallcap", "r_smallcap_rotate",
        }

        # 发布记录流转：draft -> published(生成版本) -> unpublished(下架但保留已发布版本)。
        self._publish_records: dict[str, list[ResearcherPublishRecord]] = {
            "r_trend": [
                ResearcherPublishRecord(version="v1", publish_time=now - timedelta(days=1, hours=2), status="published"),
            ],
            "r_quant": [
                ResearcherPublishRecord(version="v1", publish_time=now - timedelta(days=5), status="published"),
                ResearcherPublishRecord(version="v2", publish_time=now - timedelta(hours=12), status="published"),
            ],
            "r_smallcap": [
                ResearcherPublishRecord(version="v1", publish_time=now - timedelta(days=3), status="published"),
            ],
            "r_smallcap_rotate": [
                ResearcherPublishRecord(version="v1", publish_time=now - timedelta(hours=6), status="published"),
            ],
            "r_sentiment": [
                ResearcherPublishRecord(version="v0", publish_time=now - timedelta(days=2), status="draft"),
            ],
        }

        self._skill_options: list[ResearcherOptionItem] = [
            ResearcherOptionItem(id="skill_event_drive", name="事件驱动框架"),
            ResearcherOptionItem(id="skill_tech_analysis", name="技术分析模板"),
            ResearcherOptionItem(id="skill_short_term_sentiment", name="超短情绪因子"),
            ResearcherOptionItem(id="skill_quant_factor", name="多因子选股框架"),
            ResearcherOptionItem(id="skill_risk_management", name="风险管理体系"),
            ResearcherOptionItem(id="skill_growth_screening", name="成长股筛选引擎"),
            ResearcherOptionItem(id="skill_smallcap_rotation", name="小市值轮动因子"),
        ]
        self._knowledge_base_options: list[ResearcherOptionItem] = [
            ResearcherOptionItem(id="kb_market_daily", name="市场日报知识库"),
            ResearcherOptionItem(id="kb_chip_data", name="筹码结构知识库"),
            ResearcherOptionItem(id="kb_tick_data", name="逐笔成交知识库"),
            ResearcherOptionItem(id="kb_factor_data", name="因子数据知识库"),
            ResearcherOptionItem(id="kb_smallcap_data", name="小盘股数据知识库"),
        ]
        self._mcp_server_options: list[ResearcherOptionItem] = [
            ResearcherOptionItem(id="mcp_financial_news", name="财经新闻服务"),
            ResearcherOptionItem(id="mcp_l2_quote", name="L2行情服务"),
            ResearcherOptionItem(id="mcp_fund_flow", name="资金流监控服务"),
        ]

        # 工作台首屏样例数据，结构与预期联调字段保持一致，后续可替换为 repository 查询。
        self._workbench_hired: list[WorkbenchHiredResearcher] = [
            WorkbenchHiredResearcher(
                researcher_id="r_trend",
                avatar_url=None,
                name="市场趋势-找买",
                summary="擅长热点轮动与中线择时，提供结构化交易计划。",
                status="active",
                tags=["技术面", "事件驱动", "中线"],
                today_yield=0.0178,
                win_rate_30d=0.63,
                level="LV.2",
            ),
            WorkbenchHiredResearcher(
                researcher_id="r_quant",
                avatar_url=None,
                name="量化稳健者",
                summary="基于量化因子选股与风控体系，追求稳定阿尔法。",
                status="active",
                tags=["量化", "多因子", "低回撤"],
                today_yield=0.0045,
                win_rate_30d=0.68,
                level="LV.3",
            ),
            WorkbenchHiredResearcher(
                researcher_id="r_smallcap",
                avatar_url=None,
                name="小米研究员-雷锋",
                summary="深耕小盘成长股，擅长发掘早期高弹性标的。",
                status="active",
                tags=["小盘股", "成长", "弹性"],
                today_yield=0.0087,
                win_rate_30d=0.58,
                level="LV.2",
            ),
            WorkbenchHiredResearcher(
                researcher_id="r_smallcap_rotate",
                avatar_url=None,
                name="小市值轮动",
                summary="SG+MS+PEG三因子选股，每日调仓，内置止损与涨停管理。",
                status="active",
                tags=["小市值", "因子轮动", "量化", "每日调仓"],
                today_yield=0.0112,
                win_rate_30d=0.61,
                level="LV.2",
            ),
            WorkbenchHiredResearcher(
                researcher_id="r_sentiment",
                avatar_url=None,
                name="情绪超短-阿发",
                summary="聚焦竞价与盘口情绪，给出短线仓位与风控建议。",
                status="idle",
                tags=["情绪周期", "超短", "风控"],
                today_yield=-0.0068,
                win_rate_30d=0.54,
                level="LV.1",
            ),
        ]
        self._workbench_hot_documents: list[WorkbenchHotDocument] = [
            WorkbenchHotDocument(
                id="doc_20260418_ai_chip",
                title="AI算力链跟踪：订单边际变化与二季度预期",
                summary="覆盖服务器、交换机与光模块环节，给出乐观/中性/谨慎三情景推演。",
                researcher_name="市场趋势-找买",
                create_time=datetime(2026, 4, 18, 8, 30, tzinfo=UTC),
                view_count=1824,
                comment_count=43,
            ),
            WorkbenchHotDocument(
                id="doc_20260417_sentiment_cycle",
                title="短线情绪复盘：高位分歧后的次日策略",
                summary="从竞价强弱、炸板率与连板梯队切入，定义可执行仓位框架。",
                researcher_name="情绪超短-阿发",
                create_time=datetime(2026, 4, 17, 14, 5, tzinfo=UTC),
                view_count=1392,
                comment_count=31,
            ),
            WorkbenchHotDocument(
                id="doc_20260416_etf_flow",
                title="ETF资金流向观察：北向与行业轮动节奏",
                summary="结合成交额与资金净流，评估行业拥挤度与回撤风险。",
                researcher_name="量化稳健者",
                create_time=datetime(2026, 4, 16, 10, 20, tzinfo=UTC),
                view_count=1210,
                comment_count=19,
            ),
            WorkbenchHotDocument(
                id="doc_20260419_smallcap_rotate",
                title="小市值轮动策略日报：三因子选股与调仓执行",
                summary="SG/MS/PEG三因子融合选出10只小市值标的，附止损与涨停管理。",
                researcher_name="小市值轮动",
                create_time=datetime(2026, 4, 19, 9, 30, tzinfo=UTC),
                view_count=876,
                comment_count=22,
            ),
        ]
        self._workbench_public_rankings: list[WorkbenchPublicRankItem] = [
            WorkbenchPublicRankItem(
                researcher_id="r_trend",
                name="市场趋势-找买",
                total_asset=1785672.00,
                today_yield_rate=0.0178,
                month_yield_rate=0.094,
                risk_note="回撤控制较好，但对流动性突变较敏感。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_quant",
                name="量化稳健者",
                total_asset=1900627.00,
                today_yield_rate=0.0045,
                month_yield_rate=0.081,
                risk_note="偏趋势强化行情，震荡市信号可能增多。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_public_003",
                name="智慧选",
                total_asset=1900279.00,
                today_yield_rate=0.0060,
                month_yield_rate=0.112,
                risk_note="持仓集中度较高，需关注业绩披露期波动。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_smallcap",
                name="小米研究员-雷锋",
                total_asset=1900622.00,
                today_yield_rate=0.0087,
                month_yield_rate=0.046,
                risk_note="收益弹性高，需严格执行止损纪律。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_public_005",
                name="基本面分析-007#",
                total_asset=913627.00,
                today_yield_rate=-0.0039,
                month_yield_rate=0.026,
                risk_note="策略逻辑清晰但交易频率较低。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_public_006",
                name="桔子交易所示",
                total_asset=1814115.00,
                today_yield_rate=-0.0032,
                month_yield_rate=0.072,
                risk_note="偏好大盘蓝筹，对中小盘弹性不足。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_public_007",
                name="美好财经-A",
                total_asset=1000007.00,
                today_yield_rate=0.0060,
                month_yield_rate=0.055,
                risk_note="覆盖面广但信号密度较高。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_public_008",
                name="777",
                total_asset=1000079.00,
                today_yield_rate=0.0060,
                month_yield_rate=0.048,
                risk_note="高胜率但单笔盈利空间有限。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_public_009",
                name="演艺乐-小妹",
                total_asset=1003975.00,
                today_yield_rate=0.0060,
                month_yield_rate=0.039,
                risk_note="主攻消费行业，行业单一。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_sentiment",
                name="情绪超短-阿发",
                total_asset=952340.11,
                today_yield_rate=-0.0068,
                month_yield_rate=0.033,
                risk_note="短线操作要求严格纪律。",
            ),
            WorkbenchPublicRankItem(
                researcher_id="r_smallcap_rotate",
                name="小市值轮动",
                total_asset=1156890.00,
                today_yield_rate=0.0112,
                month_yield_rate=0.068,
                risk_note="小市值策略流动性风险较高，极端行情回撤可能较大。",
            ),
        ]
        self._workbench_quick_actions: list[WorkbenchQuickAction] = [
            WorkbenchQuickAction(
                action_key="new_chat",
                title="发起研究会话",
                description="和研究员快速讨论盘前计划或持仓调整。",
            ),
            WorkbenchQuickAction(
                action_key="create_document",
                title="新建研究文档",
                description="沉淀观点、跟踪假设并输出结构化报告。",
            ),
            WorkbenchQuickAction(
                action_key="risk_scan",
                title="一键风险体检",
                description="检查持仓暴露与近期回撤风险提示。",
            ),
        ]
        self._workbench_risk_disclaimer = (
            "以上内容仅为研究观点展示，不构成投资建议。市场有风险，投资需谨慎。"
        )

    def list_researchers(self) -> list[ResearcherSummary]:
        return [self._to_summary(item) for item in self._researchers.values()]

    def get_researcher(self, researcher_id: str) -> ResearcherDetail:
        researcher = self._researchers.get(researcher_id)
        if not researcher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")
        return researcher

    def create_researcher(self, payload: ResearcherCreateRequest) -> ResearcherDetail:
        researcher_id = f"r_{uuid4().hex[:10]}"
        now = datetime.now(tz=UTC)
        detail = ResearcherDetail(
            researcher_id=researcher_id,
            name=payload.name,
            title=payload.title,
            style=payload.style,
            status="idle",
            today_pnl=0.0,
            win_rate_30d=0.0,
            level="LV.1",
            avatar_url=None,
            description=payload.description,
            prompt=payload.prompt,
            visibility=payload.visibility,
            published_version=None,
            skills=payload.skills,
            knowledge_bases=payload.knowledge_bases,
            mcp_servers=payload.mcp_servers,
            self_drive_tasks=payload.self_drive_tasks,
            created_at=now,
            updated_at=now,
        )
        self._researchers[researcher_id] = detail
        self._mine_researcher_ids.add(researcher_id)
        self._market_meta[researcher_id] = {
            "hire_count": 0,
            "version": "v0",
            "tags": ["自定义"],
            "template_visible": False,
            "resume": "自定义研究员，待完善履历。",
        }
        self._publish_records[researcher_id] = [
            ResearcherPublishRecord(version="v0", publish_time=now, status="draft")
        ]
        return detail

    def update_researcher(self, researcher_id: str, payload: ResearcherUpdateRequest) -> ResearcherDetail:
        detail = self.get_researcher(researcher_id)
        changed = detail.model_dump()
        if payload.title is not None:
            changed["title"] = payload.title
        if payload.style is not None:
            changed["style"] = payload.style
        if payload.description is not None:
            changed["description"] = payload.description
        if payload.prompt is not None:
            changed["prompt"] = payload.prompt
        if payload.visibility is not None:
            changed["visibility"] = payload.visibility
        if payload.skills is not None:
            changed["skills"] = payload.skills
        if payload.knowledge_bases is not None:
            changed["knowledge_bases"] = payload.knowledge_bases
        if payload.mcp_servers is not None:
            changed["mcp_servers"] = payload.mcp_servers
        if payload.self_drive_tasks is not None:
            changed["self_drive_tasks"] = payload.self_drive_tasks
        changed["updated_at"] = datetime.now(tz=UTC)
        updated = ResearcherDetail(**changed)
        self._researchers[researcher_id] = updated
        return updated

    def set_status(self, researcher_id: str, status_value: str) -> ResearcherDetail:
        detail = self.get_researcher(researcher_id)
        changed = detail.model_dump()
        changed["status"] = status_value
        changed["updated_at"] = datetime.now(tz=UTC)
        updated = ResearcherDetail(**changed)
        self._researchers[researcher_id] = updated
        return updated

    def list_market(self, *, q: str | None, page: int, page_size: int) -> tuple[list[ResearcherMarketCard], int]:
        keyword = (q or "").strip().lower()
        cards: list[ResearcherMarketCard] = []
        for researcher_id, detail in self._researchers.items():
            if detail.visibility != "public":
                continue
            meta = self._market_meta.get(researcher_id)
            if not meta:
                continue
            tags = [str(item) for item in meta.get("tags", [])]
            searchable = f"{detail.name} {detail.description} {' '.join(tags)}".lower()
            if keyword and keyword not in searchable:
                continue
            cards.append(self._to_market_card(researcher_id, detail, meta))

        total = len(cards)
        start = (page - 1) * page_size
        end = start + page_size
        return cards[start:end], total

    def get_market_detail(self, researcher_id: str) -> ResearcherMarketDetail:
        detail = self.get_researcher(researcher_id)
        if detail.visibility != "public":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="市场中不存在该研究员")
        meta = self._market_meta.get(researcher_id)
        if not meta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="市场中不存在该研究员")
        card = self._to_market_card(researcher_id, detail, meta)
        return ResearcherMarketDetail(
            **card.model_dump(),
            resume=str(meta.get("resume", "")),
            prompt=detail.prompt,
        )

    def list_mine(self) -> list[ResearcherMineItem]:
        items: list[ResearcherMineItem] = []
        for researcher_id in self._mine_researcher_ids:
            detail = self._researchers.get(researcher_id)
            meta = self._market_meta.get(researcher_id)
            if not detail or not meta:
                continue
            latest_record = self._latest_publish_record(researcher_id)
            items.append(
                ResearcherMineItem(
                    id=researcher_id,
                    name=detail.name,
                    avatar=detail.avatar_url,
                    introduction=detail.description,
                    level=detail.level,
                    visibility=detail.visibility,
                    published_version=detail.published_version,
                    publish_status=latest_record.status if latest_record else "draft",
                    version=str(meta.get("version", "v0")),
                    updated_at=detail.updated_at,
                )
            )
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    def duplicate_researcher(self, researcher_id: str) -> ResearcherDetail:
        source = self.get_researcher(researcher_id)
        new_id = f"r_{uuid4().hex[:10]}"
        now = datetime.now(tz=UTC)
        duplicated = ResearcherDetail(
            researcher_id=new_id,
            name=f"{source.name} 副本",
            title=source.title,
            style=source.style,
            status="idle",
            today_pnl=0.0,
            win_rate_30d=0.0,
            level=source.level,
            avatar_url=source.avatar_url,
            description=source.description,
            prompt=source.prompt,
            # 复制后总是草稿，避免误把旧版本直接公开。
            visibility="draft",
            published_version=None,
            skills=list(source.skills),
            knowledge_bases=list(source.knowledge_bases),
            mcp_servers=list(source.mcp_servers),
            self_drive_tasks=list(source.self_drive_tasks),
            created_at=now,
            updated_at=now,
        )
        self._researchers[new_id] = duplicated
        self._mine_researcher_ids.add(new_id)
        self._market_meta[new_id] = {
            "hire_count": 0,
            "version": "v0",
            "tags": list(self._market_meta.get(researcher_id, {}).get("tags", [])),
            "template_visible": False,
            "resume": f"由 {source.name} 复制生成，待完善。",
        }
        self._publish_records[new_id] = [
            ResearcherPublishRecord(version="v0", publish_time=now, status="draft")
        ]
        return duplicated

    def publish_researcher(self, researcher_id: str) -> ResearcherPublishRecord:
        detail = self.get_researcher(researcher_id)
        meta = self._market_meta.get(researcher_id)
        if not meta:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        current_version = str(meta.get("version", "v0"))
        version_num = int(current_version.lstrip("v") or "0") + 1
        new_version = f"v{version_num}"
        now = datetime.now(tz=UTC)

        # 状态流转：发布后自动切到 public，并记录当前发布版本。
        changed = detail.model_dump()
        changed["visibility"] = "public"
        changed["published_version"] = new_version
        changed["updated_at"] = now
        self._researchers[researcher_id] = ResearcherDetail(**changed)

        meta["version"] = new_version
        record = ResearcherPublishRecord(version=new_version, publish_time=now, status="published")
        self._publish_records.setdefault(researcher_id, []).append(record)
        return record

    def unpublish_researcher(self, researcher_id: str) -> ResearcherPublishRecord:
        detail = self.get_researcher(researcher_id)
        now = datetime.now(tz=UTC)
        current_version = detail.published_version or str(self._market_meta.get(researcher_id, {}).get("version", "v0"))

        # 状态流转：下架仅变更可见性为 private，保留最后一次发布版本用于回显。
        changed = detail.model_dump()
        changed["visibility"] = "private"
        changed["updated_at"] = now
        self._researchers[researcher_id] = ResearcherDetail(**changed)

        record = ResearcherPublishRecord(version=current_version, publish_time=now, status="unpublished")
        self._publish_records.setdefault(researcher_id, []).append(record)
        return record

    def list_skill_options(self) -> list[ResearcherOptionItem]:
        return list(self._skill_options)

    def list_knowledge_base_options(self) -> list[ResearcherOptionItem]:
        return list(self._knowledge_base_options)

    def list_mcp_server_options(self) -> list[ResearcherOptionItem]:
        return list(self._mcp_server_options)

    async def test_chat(self, researcher_id: str, question: str) -> ResearcherTestChatResponse:
        """研究员测试对话 —— 使用 LLM 生成回复

        流程：
          1. 查找研究员获取 system prompt
          2. 构建消息列表（system + user）
          3. 调用 LLM client（未配置时自动降级为 mock）
        """
        detail = self.get_researcher(researcher_id)
        version_used = detail.published_version or str(
            self._market_meta.get(researcher_id, {}).get("version", "v0")
        )

        # 构建 system prompt：包含研究员角色、风格和能力描述
        system_prompt = (
            f"你是一名名叫「{detail.name}」的 AI 研究员。\n"
            f"职位：{detail.title}\n"
            f"风格：{detail.style}\n"
            f"简介：{detail.description}\n\n"
        )
        if detail.prompt:
            system_prompt += f"特殊指令：{detail.prompt}\n\n"
        system_prompt += (
            "请基于以上角色设定回答用户的问题。"
            "回复应专业、有条理，语言简洁，适当使用结构化输出。"
        )

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=question),
        ]

        llm = get_llm_client()
        answer = await llm.chat(messages)

        return ResearcherTestChatResponse(
            researcher_id=researcher_id,
            question=question,
            answer=answer,
            version_used=version_used,
            reply_time=datetime.now(tz=UTC),
        )

    def list_workbench_hired(self) -> list[WorkbenchHiredResearcher]:
        return list(self._workbench_hired)

    def list_workbench_hot_documents(self) -> list[WorkbenchHotDocument]:
        return list(self._workbench_hot_documents)

    def list_workbench_public_rankings(
        self, *, sort_by: WorkbenchRankSortBy = "today"
    ) -> list[WorkbenchPublicRankItem]:
        key_fn: Callable[[WorkbenchPublicRankItem], float]
        key_fn = (
            (lambda item: item.month_yield_rate)
            if sort_by == "month"
            else (lambda item: item.today_yield_rate)
        )
        return sorted(self._workbench_public_rankings, key=key_fn, reverse=True)

    def get_workbench_overview(self, *, sort_by: WorkbenchRankSortBy = "today") -> WorkbenchOverview:
        """聚合工作台首屏数据，预留 partial_failures 以支持局部失败降级。"""

        partial_failures: list[str] = []
        hired = self.list_workbench_hired()
        hot_documents = self.list_workbench_hot_documents()
        rankings = self.list_workbench_public_rankings(sort_by=sort_by)
        return WorkbenchOverview(
            hired=hired,
            hot_documents=hot_documents,
            rankings=rankings,
            quick_actions=list(self._workbench_quick_actions),
            risk_disclaimer=self._workbench_risk_disclaimer,
            partial_failures=partial_failures,
        )

    # ══════════════════════════════════════════════════════════════════
    # 数据库模式（async） —— 数据库就绪后由 router 层调用
    # ══════════════════════════════════════════════════════════════════

    async def async_list_researchers(self, session: AsyncSession) -> list[ResearcherSummary]:
        """从数据库查询所有研究员摘要"""
        repo = ResearcherRepository(session)
        researchers = await repo.list_all(limit=200)
        return [self._model_to_summary(r) for r in researchers]

    async def async_get_researcher(self, session: AsyncSession, researcher_id: str) -> ResearcherDetail:
        """从数据库查询研究员详情"""
        repo = ResearcherRepository(session)
        r = await repo.get_by_id(researcher_id)
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")
        return self._model_to_detail(r)

    async def async_create_researcher(
        self, session: AsyncSession, owner_id: str, payload: ResearcherCreateRequest
    ) -> ResearcherDetail:
        """在数据库创建研究员"""
        repo = ResearcherRepository(session)
        model = ResearcherModel(
            id=f"r_{uuid4().hex[:10]}",
            owner_id=owner_id,
            name=payload.name,
            title=payload.title,
            style=payload.style,
            description=payload.description,
            prompt=payload.prompt,
            visibility=payload.visibility,
            skills=payload.skills,
            knowledge_bases=payload.knowledge_bases,
            mcp_servers=payload.mcp_servers,
            self_drive_tasks=payload.self_drive_tasks,
            strategy_config=payload.strategy_config,
            tags=["自定义"],
        )
        await repo.create(model)
        await session.commit()
        return self._model_to_detail(model)

    async def async_update_researcher(
        self, session: AsyncSession, researcher_id: str, payload: ResearcherUpdateRequest
    ) -> ResearcherDetail:
        """在数据库更新研究员"""
        repo = ResearcherRepository(session)
        r = await repo.get_by_id(researcher_id)
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        # 只更新非 None 字段
        updates = {}
        if payload.title is not None:
            updates["title"] = payload.title
        if payload.style is not None:
            updates["style"] = payload.style
        if payload.description is not None:
            updates["description"] = payload.description
        if payload.prompt is not None:
            updates["prompt"] = payload.prompt
        if payload.visibility is not None:
            updates["visibility"] = payload.visibility
        if payload.skills is not None:
            updates["skills"] = payload.skills
        if payload.knowledge_bases is not None:
            updates["knowledge_bases"] = payload.knowledge_bases
        if payload.mcp_servers is not None:
            updates["mcp_servers"] = payload.mcp_servers
        if payload.self_drive_tasks is not None:
            updates["self_drive_tasks"] = payload.self_drive_tasks
        if payload.strategy_config is not None:
            updates["strategy_config"] = payload.strategy_config

        if updates:
            await repo.update(r, **updates)
            await session.commit()
        return self._model_to_detail(r)

    async def async_list_mine(self, session: AsyncSession, owner_id: str) -> list[ResearcherMineItem]:
        """从数据库查询某用户创建的研究员"""
        repo = ResearcherRepository(session)
        researchers = await repo.list_by_owner(owner_id)
        return [
            ResearcherMineItem(
                id=r.id,
                name=r.name,
                avatar=r.avatar_url,
                introduction=r.description,
                level=r.level,
                visibility=r.visibility,
                published_version=r.published_version,
                publish_status=r.publish_status,
                version=r.version,
                updated_at=r.updated_at,
            )
            for r in researchers
        ]

    async def async_list_market(
        self, session: AsyncSession, *, q: str | None, page: int, page_size: int
    ) -> tuple[list[ResearcherMarketCard], int]:
        """从数据库查询市场公开研究员"""
        repo = ResearcherRepository(session)
        researchers = await repo.list_public(limit=200)

        # 关键词过滤
        keyword = (q or "").strip().lower()
        filtered = []
        for r in researchers:
            searchable = f"{r.name} {r.description} {' '.join(r.tags)}".lower()
            if keyword and keyword not in searchable:
                continue
            filtered.append(r)

        total = len(filtered)
        start = (page - 1) * page_size
        page_items = filtered[start:start + page_size]

        cards = [
            ResearcherMarketCard(
                id=r.id,
                name=r.name,
                avatar=r.avatar_url,
                introduction=r.description,
                level=r.level,
                hire_count=r.hire_count,
                version=r.version,
                tags=r.tags,
                template_visible=r.visibility == "public",
                is_hired=False,  # 需要 user_id 来判断，后续完善
            )
            for r in page_items
        ]
        return cards, total

    async def async_publish(self, session: AsyncSession, researcher_id: str) -> ResearcherPublishRecord:
        """在数据库发布研究员"""
        repo = ResearcherRepository(session)
        r = await repo.get_by_id(researcher_id)
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        version_num = int(r.version.lstrip("v") or "0") + 1
        new_version = f"v{version_num}"
        now = datetime.now(tz=UTC)

        await repo.update(
            r,
            visibility="public",
            publish_status="published",
            published_version=new_version,
            version=new_version,
        )
        await session.commit()
        return ResearcherPublishRecord(version=new_version, publish_time=now, status="published")

    async def async_unpublish(self, session: AsyncSession, researcher_id: str) -> ResearcherPublishRecord:
        """在数据库下架研究员"""
        repo = ResearcherRepository(session)
        r = await repo.get_by_id(researcher_id)
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        now = datetime.now(tz=UTC)
        await repo.update(r, visibility="private", publish_status="unpublished")
        await session.commit()
        return ResearcherPublishRecord(
            version=r.published_version or r.version,
            publish_time=now,
            status="unpublished",
        )

    async def async_hire(self, session: AsyncSession, user_id: str, researcher_id: str) -> None:
        """在数据库记录雇佣关系，并自动创建模拟交易账户（如尚不存在）"""
        from app.models.trading import TradingAccount as AccountModel

        r_repo = ResearcherRepository(session)
        r = await r_repo.get_by_id(researcher_id)
        if not r:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        h_repo = ResearcherHireRepository(session)
        existing = await h_repo.find_hire(user_id, researcher_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已雇佣该研究员")

        hire = HireModel(
            id=f"h_{uuid4().hex[:10]}",
            user_id=user_id,
            researcher_id=researcher_id,
            status="hired",
        )
        await h_repo.create(hire)

        # 自动创建模拟交易账户（若该研究员还没有账户）
        acct_stmt = select(AccountModel).where(AccountModel.researcher_id == researcher_id)
        acct_result = await session.execute(acct_stmt)
        if acct_result.scalar_one_or_none() is None:
            initial_cash = 100_000.0
            acct = AccountModel(
                id=f"acct_{uuid4().hex[:10]}",
                user_id=user_id,
                researcher_id=researcher_id,
                total_asset=initial_cash,
                available_cash=initial_cash,
                holding_value=0.0,
                daily_pnl=0.0,
            )
            session.add(acct)

        # 更新雇佣计数
        await r_repo.update(r, hire_count=r.hire_count + 1, status="active")
        await session.commit()

    async def async_dismiss(self, session: AsyncSession, user_id: str, researcher_id: str) -> None:
        """在数据库解除雇佣关系"""
        h_repo = ResearcherHireRepository(session)
        hire = await h_repo.find_hire(user_id, researcher_id)
        if not hire:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到雇佣关系")

        await h_repo.update(hire, status="dismissed")

        r_repo = ResearcherRepository(session)
        r = await r_repo.get_by_id(researcher_id)
        if r and r.hire_count > 0:
            await r_repo.update(r, hire_count=r.hire_count - 1)
        await session.commit()

    async def async_list_workbench_hired(
        self, session: AsyncSession, user_id: str
    ) -> list[WorkbenchHiredResearcher]:
        """从数据库查询用户可见的研究员列表。

        包含两部分：
          1. 系统内定研究员（is_system=True）—— 所有用户自动可见
          2. 用户自己雇佣的非系统研究员
        """
        r_repo = ResearcherRepository(session)

        # ── 系统内定研究员（全局可见） ──
        system_stmt = select(ResearcherModel).where(ResearcherModel.is_system == True)
        system_result = await session.execute(system_stmt)
        system_researchers = system_result.scalars().all()

        seen_ids: set[str] = set()
        result: list[WorkbenchHiredResearcher] = []

        for r in system_researchers:
            seen_ids.add(r.id)
            result.append(self._researcher_to_hired_card(r))

        # ── 用户自己雇佣的研究员（补充非系统的） ──
        h_repo = ResearcherHireRepository(session)
        hires = await h_repo.list_hired_by_user(user_id)
        for h in hires:
            if h.researcher_id in seen_ids:
                continue
            r = await r_repo.get_by_id(h.researcher_id)
            if not r:
                continue
            seen_ids.add(r.id)
            result.append(self._researcher_to_hired_card(r))

        return result

    @staticmethod
    def _researcher_to_hired_card(r: ResearcherModel) -> WorkbenchHiredResearcher:
        """ORM Researcher → WorkbenchHiredResearcher schema"""
        return WorkbenchHiredResearcher(
            researcher_id=r.id,
            avatar_url=r.avatar_url,
            name=r.name,
            summary=r.description,
            status=r.status,
            tags=r.tags,
            today_yield=r.today_pnl,
            win_rate_30d=r.win_rate_30d,
            level=r.level,
        )

    async def async_list_public_rankings(
        self, session: AsyncSession, *, sort_by: WorkbenchRankSortBy = "today", limit: int = 20
    ) -> list[WorkbenchPublicRankItem]:
        """从数据库查询公开研究员收益排行榜。

        关联 trading_accounts 获取真实总资产，按 today_pnl 或 total_asset 排序。
        """
        from app.models.trading import TradingAccount

        # 根据排序方式选择排序字段
        order_col = (
            TradingAccount.daily_pnl.desc()
            if sort_by == "today"
            else TradingAccount.total_asset.desc()
        )

        stmt = (
            select(ResearcherModel, TradingAccount)
            .join(TradingAccount, TradingAccount.researcher_id == ResearcherModel.id)
            .where(ResearcherModel.visibility == "public")
            .order_by(order_col)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        rankings: list[WorkbenchPublicRankItem] = []
        for r, acct in rows:
            total = float(acct.total_asset) if acct else 100_000.0
            initial = 100_000.0  # 初始资金
            today_pnl = float(acct.daily_pnl) if acct else 0.0
            rankings.append(WorkbenchPublicRankItem(
                researcher_id=r.id,
                name=r.name,
                total_asset=total,
                today_yield_rate=today_pnl / total if total > 0 else 0.0,
                month_yield_rate=(total - initial) / initial if initial > 0 else 0.0,
                risk_note="模拟盘",
            ))
        return rankings

    async def async_get_workbench_overview(
        self, session: AsyncSession, user_id: str, *, sort_by: WorkbenchRankSortBy = "today"
    ) -> WorkbenchOverview:
        """从数据库聚合工作台首屏数据"""
        from app.models.document import Document as DocModel

        partial_failures: list[str] = []

        # ── hired ──
        hired = await self.async_list_workbench_hired(session, user_id)

        # ── hot_documents（按 view_count 降序取前 6）──
        hot_documents: list[WorkbenchHotDocument] = []
        try:
            r_repo = ResearcherRepository(session)
            stmt = select(DocModel).order_by(DocModel.view_count.desc()).limit(6)
            doc_result = await session.execute(stmt)
            docs = doc_result.scalars().all()
            for d in docs:
                r = await r_repo.get_by_id(d.researcher_id)
                hot_documents.append(WorkbenchHotDocument(
                    id=d.id,
                    title=d.title,
                    summary=d.summary,
                    researcher_name=r.name if r else "未知",
                    create_time=d.created_at,
                    view_count=d.view_count,
                    comment_count=d.comment_count,
                ))
        except Exception:
            partial_failures.append("hot_documents")

        # ── rankings ──
        rankings: list[WorkbenchPublicRankItem] = []
        try:
            rankings = await self.async_list_public_rankings(session, sort_by=sort_by)
        except Exception:
            partial_failures.append("rankings")

        return WorkbenchOverview(
            hired=hired,
            hot_documents=hot_documents,
            rankings=rankings,
            quick_actions=list(self._workbench_quick_actions),
            risk_disclaimer=self._workbench_risk_disclaimer,
            partial_failures=partial_failures,
        )

    # ── ORM → Schema 转换辅助方法 ──

    @staticmethod
    def _model_to_summary(r: ResearcherModel) -> ResearcherSummary:
        """将 ORM Researcher 对象转为 ResearcherSummary schema"""
        return ResearcherSummary(
            researcher_id=r.id,
            name=r.name,
            title=r.title,
            style=r.style,
            status=r.status,
            today_pnl=r.today_pnl,
            win_rate_30d=r.win_rate_30d,
            level=r.level,
        )

    @staticmethod
    def _model_to_detail(r: ResearcherModel) -> ResearcherDetail:
        """将 ORM Researcher 对象转为 ResearcherDetail schema"""
        return ResearcherDetail(
            researcher_id=r.id,
            name=r.name,
            title=r.title,
            style=r.style,
            status=r.status,
            today_pnl=r.today_pnl,
            win_rate_30d=r.win_rate_30d,
            level=r.level,
            avatar_url=r.avatar_url,
            description=r.description,
            prompt=r.prompt,
            visibility=r.visibility,
            published_version=r.published_version,
            skills=r.skills,
            knowledge_bases=r.knowledge_bases,
            mcp_servers=r.mcp_servers,
            self_drive_tasks=r.self_drive_tasks,
            strategy_config=r.strategy_config,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )

    # ══════════════════════════════════════════════════════════════════
    # 内部辅助方法（mock 模式使用）
    # ══════════════════════════════════════════════════════════════════

    def _latest_publish_record(self, researcher_id: str) -> ResearcherPublishRecord | None:
        records = self._publish_records.get(researcher_id, [])
        if not records:
            return None
        return records[-1]

    def _to_market_card(
        self, researcher_id: str, detail: ResearcherDetail, meta: dict[str, object]
    ) -> ResearcherMarketCard:
        return ResearcherMarketCard(
            id=researcher_id,
            name=detail.name,
            avatar=detail.avatar_url,
            introduction=detail.description,
            level=detail.level,
            hire_count=int(meta.get("hire_count", 0)),
            version=str(meta.get("version", "v0")),
            tags=[str(item) for item in meta.get("tags", [])],
            template_visible=bool(meta.get("template_visible", False)),
            is_hired=researcher_id in self._hired_researcher_ids,
        )

    @staticmethod
    def _to_summary(detail: ResearcherDetail) -> ResearcherSummary:
        return ResearcherSummary(**detail.model_dump(include=set(ResearcherSummary.model_fields.keys())))
