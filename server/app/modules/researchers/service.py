"""研究员领域服务。"""
from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime
import logging
from textwrap import shorten
from uuid import uuid4

from fastapi import HTTPException, status
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Load, load_only, noload

from app.core.container import get_container
from app.integrations.akshare.client import get_limit_up_pool, get_live_news_merged, run_sync
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.researcher import Researcher as ResearcherModel
from app.models.researcher import ResearcherHire as HireModel
from app.modules.page_cache import delete_cached, load_cached, save_cached
from app.repositories.researcher_repo import ResearcherHireRepository, ResearcherRepository

from app.modules.researchers.schemas import (
    ResearcherCreateRequest,
    ResearcherDetail,
    ResearcherMarketCard,
    ResearcherMarketDetail,
    ResearcherMineItem,
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


logger = logging.getLogger(__name__)
WORKBENCH_OVERVIEW_CACHE_TTL_SECONDS = 30
_workbench_overview_cache: dict[str, tuple[float, WorkbenchOverview]] = {}
_WORKBENCH_OVERVIEW_CACHE_ADAPTER = TypeAdapter(WorkbenchOverview)


def _workbench_overview_cache_key(user_id: str, sort_by: WorkbenchRankSortBy) -> str:
    return f"researchers:workbench:overview:{user_id}:{sort_by}"


def _set_workbench_overview_memory_cache(
    user_id: str,
    sort_by: WorkbenchRankSortBy,
    data: WorkbenchOverview,
) -> None:
    _workbench_overview_cache[f"{user_id}:{sort_by}"] = (
        time.monotonic() + WORKBENCH_OVERVIEW_CACHE_TTL_SECONDS,
        data,
    )


async def _load_workbench_overview_redis_cache(
    user_id: str,
    sort_by: WorkbenchRankSortBy,
) -> WorkbenchOverview | None:
    try:
        redis = get_container().redis.get_client()
        data = await load_cached(redis, _workbench_overview_cache_key(user_id, sort_by), _WORKBENCH_OVERVIEW_CACHE_ADAPTER)
        if data is not None:
            _set_workbench_overview_memory_cache(user_id, sort_by, data)
        return data
    except Exception:
        logger.warning("[研究员工作台] Redis 缓存读取失败", exc_info=True)
        return None


async def _save_workbench_overview_redis_cache(
    user_id: str,
    sort_by: WorkbenchRankSortBy,
    data: WorkbenchOverview,
) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(
            redis,
            _workbench_overview_cache_key(user_id, sort_by),
            data,
            ttl_seconds=WORKBENCH_OVERVIEW_CACHE_TTL_SECONDS * 4,
        )
    except Exception:
        logger.warning("[研究员工作台] Redis 缓存写入失败", exc_info=True)


async def invalidate_workbench_overview_cache(user_id: str | None = None) -> None:
    prefixes = [f"{user_id}:"] if user_id else [""]
    for key in list(_workbench_overview_cache.keys()):
        if any(key.startswith(prefix) for prefix in prefixes):
            _workbench_overview_cache.pop(key, None)

    if not user_id:
        return
    try:
        redis = get_container().redis.get_client()
        for sort_by in ("today", "month"):
            await delete_cached(redis, _workbench_overview_cache_key(user_id, sort_by))
    except Exception:
        logger.warning("[研究员工作台] Redis 缓存失效失败", exc_info=True)


class ResearcherService:
    """研究员领域服务，只保留真实数据库路径。"""

    def __init__(self) -> None:
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
        self._workbench_risk_disclaimer = "以上内容仅为研究观点展示，不构成投资建议。市场有风险，投资需谨慎。"

    async def async_list_researchers(self, session: AsyncSession) -> list[ResearcherSummary]:
        repo = ResearcherRepository(session)
        researchers = await repo.list_all(limit=200)
        return [self._model_to_summary(item) for item in researchers]

    async def async_get_researcher(self, session: AsyncSession, researcher_id: str) -> ResearcherDetail:
        repo = ResearcherRepository(session)
        researcher = await repo.get_by_id(researcher_id)
        if not researcher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")
        return self._model_to_detail(researcher)

    async def async_get_market_detail(
        self, session: AsyncSession, researcher_id: str
    ) -> ResearcherMarketDetail:
        repo = ResearcherRepository(session)
        researcher = await repo.get_by_id(researcher_id)
        if not researcher or researcher.visibility != "public":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="市场中不存在该研究员")

        return ResearcherMarketDetail(
            id=researcher.id,
            name=researcher.name,
            avatar=researcher.avatar_url,
            introduction=researcher.description,
            level=researcher.level,
            hire_count=researcher.hire_count,
            version=researcher.version,
            tags=list(researcher.tags or []),
            template_visible=True,
            is_hired=False,
            resume="",
            prompt=researcher.prompt,
        )

    async def async_create_researcher(
        self, session: AsyncSession, owner_id: str, payload: ResearcherCreateRequest
    ) -> ResearcherDetail:
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
        await invalidate_workbench_overview_cache(user_id)
        return self._model_to_detail(model)

    async def async_update_researcher(
        self, session: AsyncSession, researcher_id: str, payload: ResearcherUpdateRequest
    ) -> ResearcherDetail:
        repo = ResearcherRepository(session)
        researcher = await repo.get_by_id(researcher_id)
        if not researcher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        updates: dict[str, object] = {}
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
            await repo.update(researcher, **updates)
            await session.commit()
            await invalidate_workbench_overview_cache(researcher.owner_id)
        return self._model_to_detail(researcher)

    async def async_duplicate_researcher(
        self, session: AsyncSession, researcher_id: str, owner_id: str
    ) -> ResearcherDetail:
        repo = ResearcherRepository(session)
        source = await repo.get_by_id(researcher_id)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        duplicated = ResearcherModel(
            id=f"r_{uuid4().hex[:10]}",
            owner_id=owner_id,
            name=f"{source.name} 副本",
            title=source.title,
            style=source.style,
            description=source.description,
            prompt=source.prompt,
            avatar_url=source.avatar_url,
            status="idle",
            visibility="draft",
            publish_status="draft",
            published_version=None,
            version="v0",
            level=source.level,
            today_pnl=0.0,
            win_rate_30d=0.0,
            skills=list(source.skills or []),
            knowledge_bases=list(source.knowledge_bases or []),
            mcp_servers=list(source.mcp_servers or []),
            tags=list(source.tags or []),
            self_drive_tasks=list(source.self_drive_tasks or []),
            strategy_config=source.strategy_config,
            is_system=False,
            hire_count=0,
        )
        await repo.create(duplicated)
        await session.commit()
        await invalidate_workbench_overview_cache(owner_id)
        return self._model_to_detail(duplicated)

    async def async_list_mine(self, session: AsyncSession, owner_id: str) -> list[ResearcherMineItem]:
        repo = ResearcherRepository(session)
        researchers = await repo.list_by_owner(owner_id)
        return [
            ResearcherMineItem(
                id=researcher.id,
                name=researcher.name,
                avatar=researcher.avatar_url,
                introduction=researcher.description,
                level=researcher.level,
                visibility=researcher.visibility,
                published_version=researcher.published_version,
                publish_status=researcher.publish_status,
                version=researcher.version,
                updated_at=researcher.updated_at,
            )
            for researcher in researchers
        ]

    async def async_list_market(
        self, session: AsyncSession, *, q: str | None, page: int, page_size: int
    ) -> tuple[list[ResearcherMarketCard], int]:
        repo = ResearcherRepository(session)
        researchers = await repo.list_public(limit=200)

        keyword = (q or "").strip().lower()
        filtered: list[ResearcherModel] = []
        for researcher in researchers:
            tags = researcher.tags or []
            searchable = f"{researcher.name} {researcher.description} {' '.join(tags)}".lower()
            if keyword and keyword not in searchable:
                continue
            filtered.append(researcher)

        total = len(filtered)
        start = (page - 1) * page_size
        page_items = filtered[start:start + page_size]

        cards = [
            ResearcherMarketCard(
                id=researcher.id,
                name=researcher.name,
                avatar=researcher.avatar_url,
                introduction=researcher.description,
                level=researcher.level,
                hire_count=researcher.hire_count,
                version=researcher.version,
                tags=list(researcher.tags or []),
                template_visible=researcher.visibility == "public",
                is_hired=False,
            )
            for researcher in page_items
        ]
        return cards, total

    async def async_publish(self, session: AsyncSession, researcher_id: str) -> ResearcherPublishRecord:
        repo = ResearcherRepository(session)
        researcher = await repo.get_by_id(researcher_id)
        if not researcher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        version_num = int(researcher.version.lstrip("v") or "0") + 1
        new_version = f"v{version_num}"
        publish_time = datetime.now(tz=UTC)

        await repo.update(
            researcher,
            visibility="public",
            publish_status="published",
            published_version=new_version,
            version=new_version,
        )
        await session.commit()
        await invalidate_workbench_overview_cache(researcher.owner_id)
        return ResearcherPublishRecord(version=new_version, publish_time=publish_time, status="published")

    async def async_unpublish(self, session: AsyncSession, researcher_id: str) -> ResearcherPublishRecord:
        repo = ResearcherRepository(session)
        researcher = await repo.get_by_id(researcher_id)
        if not researcher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        publish_time = datetime.now(tz=UTC)
        await repo.update(researcher, visibility="private", publish_status="unpublished")
        await session.commit()
        await invalidate_workbench_overview_cache(researcher.owner_id)
        return ResearcherPublishRecord(
            version=researcher.published_version or researcher.version,
            publish_time=publish_time,
            status="unpublished",
        )

    async def async_hire(self, session: AsyncSession, user_id: str, researcher_id: str) -> None:
        from app.models.trading import TradingAccount as AccountModel

        researcher_repo = ResearcherRepository(session)
        researcher = await researcher_repo.get_by_id(researcher_id)
        if not researcher:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")

        hire_repo = ResearcherHireRepository(session)
        existing = await hire_repo.find_hire(user_id, researcher_id)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="已雇佣该研究员")

        hire = HireModel(
            id=f"h_{uuid4().hex[:10]}",
            user_id=user_id,
            researcher_id=researcher_id,
            status="hired",
        )
        await hire_repo.create(hire)

        account_stmt = select(AccountModel).where(AccountModel.researcher_id == researcher_id)
        account_result = await session.execute(account_stmt)
        if account_result.scalar_one_or_none() is None:
            initial_cash = 1_000_000.0
            account = AccountModel(
                id=f"acct_{uuid4().hex[:10]}",
                user_id=user_id,
                researcher_id=researcher_id,
                total_asset=initial_cash,
                available_cash=initial_cash,
                holding_value=0.0,
                daily_pnl=0.0,
            )
            session.add(account)

        await researcher_repo.update(researcher, hire_count=researcher.hire_count + 1, status="active")
        await session.commit()
        await invalidate_workbench_overview_cache(user_id)

    async def async_dismiss(self, session: AsyncSession, user_id: str, researcher_id: str) -> None:
        hire_repo = ResearcherHireRepository(session)
        hire = await hire_repo.find_hire(user_id, researcher_id)
        if not hire:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未找到雇佣关系")

        await hire_repo.update(hire, status="dismissed")

        researcher_repo = ResearcherRepository(session)
        researcher = await researcher_repo.get_by_id(researcher_id)
        if researcher and researcher.hire_count > 0:
            await researcher_repo.update(researcher, hire_count=researcher.hire_count - 1)
        await session.commit()
        await invalidate_workbench_overview_cache(user_id)

    async def async_list_workbench_hired(
        self, session: AsyncSession, user_id: str
    ) -> list[WorkbenchHiredResearcher]:
        from app.models.trading import TradingAccount

        researcher_options = self._researcher_card_load_options()
        hired_subquery = (
            select(HireModel.researcher_id)
            .where(
                HireModel.user_id == user_id,
                HireModel.status == "hired",
            )
        )
        stmt = (
            select(ResearcherModel, TradingAccount)
            .outerjoin(
                TradingAccount,
                (TradingAccount.researcher_id == ResearcherModel.id)
                & (TradingAccount.user_id == user_id),
            )
            .where(
                (ResearcherModel.is_system.is_(True))
                | (ResearcherModel.id.in_(hired_subquery))
            )
            .order_by(ResearcherModel.is_system.desc(), ResearcherModel.name.asc())
            .options(
                *researcher_options,
                Load(TradingAccount).load_only(
                    TradingAccount.total_asset,
                    TradingAccount.daily_pnl,
                ),
            )
        )
        query_result = await session.execute(stmt)
        rows = query_result.all()
        account_ids = [account.id for _, account in rows if account is not None]
        account_replays = await self._load_account_replays(session, account_ids)

        seen_ids: set[str] = set()
        result: list[WorkbenchHiredResearcher] = []
        for researcher, account in rows:
            if researcher.id in seen_ids:
                continue
            seen_ids.add(researcher.id)
            result.append(
                self._researcher_to_hired_card(
                    researcher,
                    account,
                    replay=account_replays.get(account.id) if account is not None else None,
                )
            )

        return result

    @staticmethod
    def _researcher_card_load_options() -> tuple[Load, ...]:
        """工作台卡片只需要轻字段，避免自动 selectin 关系拖慢首屏。"""
        return (
            load_only(
                ResearcherModel.id,
                ResearcherModel.avatar_url,
                ResearcherModel.name,
                ResearcherModel.description,
                ResearcherModel.status,
                ResearcherModel.tags,
                ResearcherModel.today_pnl,
                ResearcherModel.win_rate_30d,
                ResearcherModel.level,
            ),
            noload(ResearcherModel.hires),
            noload(ResearcherModel.documents),
        )

    @staticmethod
    def _researcher_to_hired_card(
        researcher: ResearcherModel,
        account: object | None = None,
        replay: object | None = None,
    ) -> WorkbenchHiredResearcher:
        daily_pnl: float | None = None
        today_yield_rate: float | None = None
        month_yield_rate: float | None = None
        total_asset: float | None = None
        if account is not None:
            metrics = ResearcherService._trading_account_view_metrics(account, replay=replay)
            total_asset = metrics["total_asset"]
            daily_pnl = metrics["daily_pnl"]
            today_start_asset = metrics["today_start_asset"]
            today_yield_rate = daily_pnl / today_start_asset if today_start_asset > 0 else 0.0
            month_yield_rate = metrics["month_yield_rate"]

        return WorkbenchHiredResearcher(
            researcher_id=researcher.id,
            avatar_url=researcher.avatar_url,
            name=researcher.name,
            summary=researcher.description,
            status=researcher.status,
            tags=list(researcher.tags or []),
            today_yield=daily_pnl,
            today_yield_rate=today_yield_rate,
            month_yield_rate=month_yield_rate,
            total_asset=total_asset,
            win_rate_30d=None,
            has_trading_account=account is not None,
            level=researcher.level,
        )

    @staticmethod
    def _trading_account_view_metrics(
        account: object,
        *,
        replay: object | None = None,
    ) -> dict[str, float]:
        from app.modules.trading.schemas import DEFAULT_INITIAL_CAPITAL
        from app.modules.trading.service import TradingService

        initial_capital = DEFAULT_INITIAL_CAPITAL
        total_asset = round(float(getattr(account, "total_asset", initial_capital)), 2)
        account_daily_pnl = getattr(account, "daily_pnl", None)
        daily_pnl = (
            round(float(account_daily_pnl), 2)
            if account_daily_pnl is not None
            else TradingService._derive_recent_pnl(
                total_asset=total_asset,
                initial_capital=initial_capital,
                replay=replay,  # type: ignore[arg-type]
            )
        )
        today_start_asset = total_asset - daily_pnl
        return {
            "total_asset": total_asset,
            "daily_pnl": daily_pnl,
            "today_start_asset": today_start_asset,
            "today_yield_rate": daily_pnl / today_start_asset if today_start_asset > 0 else 0.0,
            "month_yield_rate": (total_asset - initial_capital) / initial_capital
            if initial_capital > 0
            else 0.0,
        }

    async def _load_account_replays(
        self,
        session: AsyncSession,
        account_ids: list[str],
    ) -> dict[str, object]:
        """批量加载成交并按账户回放，给工作台复用交易详情页的收益口径。"""
        if not account_ids:
            return {}

        from app.models.trading import TradeRecord as RecordModel
        from app.modules.trading.service import TradingService

        unique_ids = sorted(set(account_ids))
        stmt = (
            select(RecordModel)
            .where(RecordModel.account_id.in_(unique_ids))
            .order_by(RecordModel.account_id.asc(), RecordModel.created_at.asc())
            .options(
                load_only(
                    RecordModel.id,
                    RecordModel.account_id,
                    RecordModel.symbol,
                    RecordModel.name,
                    RecordModel.side,
                    RecordModel.quantity,
                    RecordModel.price,
                    RecordModel.commission,
                    RecordModel.created_at,
                )
            )
        )
        result = await session.execute(stmt)
        records = list(result.scalars().all())
        records_by_account: dict[str, list[RecordModel]] = defaultdict(list)
        for record in records:
            records_by_account[record.account_id].append(record)

        trading_service = TradingService()
        return {
            account_id: trading_service._replay_records(records_by_account.get(account_id, []))
            for account_id in unique_ids
        }

    async def async_list_public_rankings(
        self, session: AsyncSession, *, sort_by: WorkbenchRankSortBy = "today", limit: int = 20
    ) -> list[WorkbenchPublicRankItem]:
        from app.models.trading import TradingAccount

        stmt = (
            select(ResearcherModel, TradingAccount)
            .join(TradingAccount, TradingAccount.researcher_id == ResearcherModel.id)
            .where(ResearcherModel.visibility == "public")
            .options(
                Load(ResearcherModel).load_only(
                    ResearcherModel.id,
                    ResearcherModel.name,
                ),
                Load(ResearcherModel).noload(ResearcherModel.hires),
                Load(ResearcherModel).noload(ResearcherModel.documents),
                Load(TradingAccount).load_only(
                    TradingAccount.total_asset,
                    TradingAccount.daily_pnl,
                ),
            )
        )
        result = await session.execute(stmt)
        rows = result.all()
        account_replays = await self._load_account_replays(
            session,
            [account.id for _, account in rows],
        )

        rankings: list[WorkbenchPublicRankItem] = []
        for researcher, account in rows:
            metrics = self._trading_account_view_metrics(
                account,
                replay=account_replays.get(account.id),
            )
            rankings.append(
                WorkbenchPublicRankItem(
                    researcher_id=researcher.id,
                    name=researcher.name,
                    total_asset=metrics["total_asset"],
                    today_yield_rate=metrics["today_yield_rate"],
                    month_yield_rate=metrics["month_yield_rate"],
                    risk_note="模拟盘",
                )
            )

        if sort_by == "today":
            rankings.sort(key=lambda item: item.today_yield_rate, reverse=True)
        else:
            rankings.sort(key=lambda item: item.month_yield_rate, reverse=True)
        return rankings[:limit]

    async def async_list_workbench_hot_documents(
        self, session: AsyncSession, *, limit: int = 6
    ) -> list[WorkbenchHotDocument]:
        """工作台热门文档。

        这个方法同时服务独立接口和 overview 聚合接口，避免两个路径各自实现一份查询逻辑。
        """
        from app.models.document import Document as DocModel

        stmt = (
            select(DocModel)
            .order_by(DocModel.created_at.desc())
            .limit(limit)
            .options(
                load_only(
                    DocModel.id,
                    DocModel.researcher_id,
                    DocModel.title,
                    DocModel.summary,
                    DocModel.view_count,
                    DocModel.comment_count,
                    DocModel.created_at,
                ),
                noload(DocModel.researcher),
            )
        )
        document_result = await session.execute(stmt)
        documents = list(document_result.scalars().all())
        researcher_ids = sorted({document.researcher_id for document in documents})
        researcher_names: dict[str, str] = {}
        if researcher_ids:
            researcher_stmt = (
                select(ResearcherModel.id, ResearcherModel.name)
                .where(ResearcherModel.id.in_(researcher_ids))
            )
            researcher_result = await session.execute(researcher_stmt)
            researcher_names = {row.id: row.name for row in researcher_result.all()}

        hot_documents: list[WorkbenchHotDocument] = []
        for document in documents:
            hot_documents.append(
                WorkbenchHotDocument(
                    id=document.id,
                    title=document.title,
                    summary=document.summary,
                    researcher_name=researcher_names.get(document.researcher_id, "未知"),
                    create_time=document.created_at,
                    view_count=None,
                    comment_count=None,
                    metrics_ready=False,
                    is_vip_only=document.doc_type in {"analysis", "stock"},
                )
            )
        return hot_documents

    async def async_test_chat(
        self, session: AsyncSession, researcher_id: str, question: str
    ) -> ResearcherTestChatResponse:
        detail = await self.async_get_researcher(session, researcher_id)
        version_used = detail.published_version or "v0"

        system_prompt = (
            f"你是一名名叫「{detail.name}」的 AI 研究员。\n"
            f"职位：{detail.title}\n"
            f"风格：{detail.style}\n"
            f"简介：{detail.description}\n\n"
        )
        if detail.prompt:
            system_prompt += f"特殊指令：{detail.prompt}\n\n"
        system_prompt += "请基于以上角色设定回答用户的问题。回复应专业、有条理，语言简洁，适当使用结构化输出。"

        messages = [
            LLMMessage(role="system", content=system_prompt),
            LLMMessage(role="user", content=question),
        ]

        llm = get_llm_client()
        if llm.is_configured:
            answer = await llm.chat(messages)
        else:
            answer = await run_sync(self._build_test_chat_fallback_answer, detail, question)
        return ResearcherTestChatResponse(
            researcher_id=researcher_id,
            question=question,
            answer=answer,
            version_used=version_used,
            reply_time=datetime.now(tz=UTC),
        )

    @staticmethod
    def _build_test_chat_fallback_answer(detail: ResearcherDetail, question: str) -> str:
        """LLM 未配置时，用 AkShare 市场快照生成可用的结构化投研答复。"""
        pool = get_limit_up_pool()
        live_news = get_live_news_merged()

        total_limit_up = len(pool)
        max_board = max((item.consecutive for item in pool), default=0)
        leaders = sorted(pool, key=lambda item: (item.consecutive, item.amount), reverse=True)[:5]
        top_news = live_news[:3]

        leader_text = "、".join(
            f"{item.name}({item.symbol}){item.consecutive}板" for item in leaders
        ) or "暂无涨停龙头数据"
        news_text = "\n".join(
            f"- {shorten(item.title, width=42, placeholder='...')}" for item in top_news
        ) or "- 暂无实时快讯"

        mood = "偏强" if total_limit_up >= 60 else "中性偏弱" if total_limit_up < 30 else "中性"

        return (
            f"我是「{detail.name}」，当前按「{detail.style}」框架回答：\n\n"
            f"**问题识别**：{question}\n\n"
            f"**市场快照**：当前涨停 {total_limit_up} 家，最高 {max_board} 连板，短线情绪{mood}。"
            f"领涨线索包括：{leader_text}。\n\n"
            f"**最新催化**：\n{news_text}\n\n"
            "**研判**：在 LLM 深度推理未启用时，我先用实时快讯和涨停结构做降级判断。"
            "如果问题涉及个股，优先检查它是否和当前领涨题材、政策催化、成交承接同向；"
            "如果只靠单条消息驱动、没有板块涨停扩散，仓位应降低。\n\n"
            "**执行建议**：\n"
            "1. 先确认题材是否有 3 家以上同向涨停或核心股主动放量。\n"
            "2. 若已有持仓，优先用分批止盈/移动止损管理，不在情绪高点一次性加仓。\n"
            "3. 若准备新开仓，等待开盘后 30-60 分钟确认承接，再用小仓位试错。\n\n"
            "以上为基于公开行情与资讯的 AI 观察，不构成投资建议。"
        )

    async def async_get_workbench_overview(
        self, session: AsyncSession, user_id: str, *, sort_by: WorkbenchRankSortBy = "today"
    ) -> WorkbenchOverview:
        cache_key = f"{user_id}:{sort_by}"
        cached = _workbench_overview_cache.get(cache_key)
        now = time.monotonic()
        if cached and cached[0] > now:
            return cached[1]

        redis_cached = await _load_workbench_overview_redis_cache(user_id, sort_by)
        if redis_cached is not None:
            return redis_cached

        partial_failures: list[str] = []

        # 三个查询共用同一个 session（单连接），无法真正并行；
        # 若未来需要并行，可为每个查询创建独立 session。
        # 当前主要性能瓶颈已通过消除排行榜 N+1 replay 解决。
        hired = await self.async_list_workbench_hired(session, user_id)

        hot_documents: list[WorkbenchHotDocument] = []
        try:
            hot_documents = await self.async_list_workbench_hot_documents(session)
        except Exception:
            partial_failures.append("hot_documents")

        rankings: list[WorkbenchPublicRankItem] = []
        try:
            rankings = await self.async_list_public_rankings(session, sort_by=sort_by)
        except Exception:
            partial_failures.append("rankings")

        overview = WorkbenchOverview(
            hired=hired,
            hot_documents=hot_documents,
            rankings=rankings,
            quick_actions=list(self._workbench_quick_actions),
            risk_disclaimer=self._workbench_risk_disclaimer,
            partial_failures=partial_failures,
        )
        _set_workbench_overview_memory_cache(user_id, sort_by, overview)
        await _save_workbench_overview_redis_cache(user_id, sort_by, overview)
        return overview

    @staticmethod
    def _model_to_summary(researcher: ResearcherModel) -> ResearcherSummary:
        return ResearcherSummary(
            researcher_id=researcher.id,
            name=researcher.name,
            title=researcher.title,
            style=researcher.style,
            status=researcher.status,
            today_pnl=researcher.today_pnl,
            win_rate_30d=researcher.win_rate_30d,
            level=researcher.level,
        )

    @staticmethod
    def _model_to_detail(researcher: ResearcherModel) -> ResearcherDetail:
        return ResearcherDetail(
            researcher_id=researcher.id,
            name=researcher.name,
            title=researcher.title,
            style=researcher.style,
            status=researcher.status,
            today_pnl=researcher.today_pnl,
            win_rate_30d=researcher.win_rate_30d,
            level=researcher.level,
            avatar_url=researcher.avatar_url,
            description=researcher.description,
            prompt=researcher.prompt,
            visibility=researcher.visibility,
            published_version=researcher.published_version,
            skills=list(researcher.skills or []),
            knowledge_bases=list(researcher.knowledge_bases or []),
            mcp_servers=list(researcher.mcp_servers or []),
            self_drive_tasks=list(researcher.self_drive_tasks or []),
            strategy_config=researcher.strategy_config,
            created_at=researcher.created_at,
            updated_at=researcher.updated_at,
        )
