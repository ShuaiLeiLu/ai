"""
研究员路由

优先返回真实数据库数据。
未接入真实数据源时，仅返回空结果或明确错误。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.container import get_container
from app.core.security import get_current_user_id
from app.modules.page_cache import delete_cached, load_cached, save_cached
from app.modules.researchers.schemas import (
    ResearcherCreateRequest,
    ResearcherDetail,
    ResearcherMarketCard,
    ResearcherMarketDetail,
    ResearcherMineItem,
    ResearcherOptionItem,
    ResearcherPublishRecord,
    ResearcherSummary,
    ResearcherTestChatRequest,
    ResearcherTestChatResponse,
    ResearcherUpdateRequest,
    WorkbenchHotDocument,
    WorkbenchHiredResearcher,
    WorkbenchOverview,
    WorkbenchPublicRankItem,
    WorkbenchRankSortBy,
)
from app.modules.researchers.service import ResearcherService
from app.schemas.common import ApiResponse, ListResponse, OperationResponse

router = APIRouter(prefix="/researchers", tags=["researchers"])
service = ResearcherService()
_CACHE_TTL_SECONDS = 120
_SUMMARY_LIST_ADAPTER = TypeAdapter(list[ResearcherSummary])
_MARKET_LIST_ADAPTER = TypeAdapter(dict)
_MARKET_DETAIL_ADAPTER = TypeAdapter(ResearcherMarketDetail)
_MINE_LIST_ADAPTER = TypeAdapter(list[ResearcherMineItem])
_DETAIL_ADAPTER = TypeAdapter(ResearcherDetail)
_HIRED_LIST_ADAPTER = TypeAdapter(list[WorkbenchHiredResearcher])
_HOT_DOCUMENTS_ADAPTER = TypeAdapter(list[WorkbenchHotDocument])
_RANK_LIST_ADAPTER = TypeAdapter(list[WorkbenchPublicRankItem])


async def _load_researcher_cache(name: str, adapter: TypeAdapter):
    try:
        redis = get_container().redis.get_client()
        return await load_cached(redis, name, adapter)
    except Exception:
        return None


async def _save_researcher_cache(name: str, data: object) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, name, data, ttl_seconds=_CACHE_TTL_SECONDS)
    except Exception:
        return


async def _delete_researcher_cache(*names: str) -> None:
    try:
        redis = get_container().redis.get_client()
        for name in names:
            await delete_cached(redis, name)
    except Exception:
        return


def _market_cache_name(q: str | None, page: int, page_size: int) -> str:
    return f"researchers:market:q={(q or '').strip()}:page={page}:size={page_size}"


def _mine_cache_name(user_id: str) -> str:
    return f"researchers:mine:{user_id}"


def _detail_cache_name(researcher_id: str) -> str:
    return f"researchers:detail:{researcher_id}"


async def _invalidate_researcher_user_cache(user_id: str | None, researcher_id: str | None = None) -> None:
    names: list[str] = []
    if user_id:
        names.append(_mine_cache_name(user_id))
    if researcher_id:
        names.append(_detail_cache_name(researcher_id))
        names.append(f"researchers:market-detail:{researcher_id}")
    await _delete_researcher_cache(*names)


def _empty_workbench_overview() -> WorkbenchOverview:
    return WorkbenchOverview(
        hired=[],
        hot_documents=[],
        rankings=[],
        quick_actions=[],
        risk_disclaimer="",
        partial_failures=["database_unavailable"],
    )


@router.get("")
async def list_researchers(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherSummary]]:
    """查询所有研究员摘要。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cached = await _load_researcher_cache("researchers:list", _SUMMARY_LIST_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_researchers(session)
    await _save_researcher_cache("researchers:list", items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/market")
async def list_market(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherMarketCard]]:
    """市场研究员列表。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _market_cache_name(q, page, page_size)
    cached = await _load_researcher_cache(cache_name, _MARKET_LIST_ADAPTER)
    if isinstance(cached, dict):
        items = TypeAdapter(list[ResearcherMarketCard]).validate_python(cached.get("items", []))
        total = int(cached.get("total", len(items)))
        return ApiResponse(data=ListResponse(items=items, total=total))
    items, total = await service.async_list_market(session, q=q, page=page, page_size=page_size)
    await _save_researcher_cache(cache_name, {"items": items, "total": total})
    return ApiResponse(data=ListResponse(items=items, total=total))


@router.get("/market/{researcher_id}")
async def market_detail(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherMarketDetail]:
    """市场研究员详情。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    cache_name = f"researchers:market-detail:{researcher_id}"
    cached = await _load_researcher_cache(cache_name, _MARKET_DETAIL_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_market_detail(session, researcher_id)
    await _save_researcher_cache(cache_name, data)
    return ApiResponse(data=data)


@router.get("/mine")
async def list_mine(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherMineItem]]:
    """我的研究员列表。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _mine_cache_name(user_id)
    cached = await _load_researcher_cache(cache_name, _MINE_LIST_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_mine(session, user_id)
    await _save_researcher_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/options/skills")
async def list_skill_options() -> ApiResponse[ListResponse[ResearcherOptionItem]]:
    """技能选项。"""
    items = [
        ResearcherOptionItem(id="trade_reflection", name="交易复盘与次日展望"),
    ]
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/options/knowledge-bases")
async def list_knowledge_base_options() -> ApiResponse[ListResponse[ResearcherOptionItem]]:
    """知识库选项。"""
    items: list[ResearcherOptionItem] = []
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/options/mcp-servers")
async def list_mcp_server_options() -> ApiResponse[ListResponse[ResearcherOptionItem]]:
    """MCP 服务器选项。"""
    items: list[ResearcherOptionItem] = []
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/hired")
async def workbench_hired(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchHiredResearcher]]:
    """工作台 —— 已雇佣研究员列表。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = f"researchers:workbench:hired:{user_id}"
    cached = await _load_researcher_cache(cache_name, _HIRED_LIST_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_workbench_hired(session, user_id)
    await _save_researcher_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/hot-documents")
async def workbench_hot_documents(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchHotDocument]]:
    """工作台 —— 热门文档。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))

    cached = await _load_researcher_cache("researchers:workbench:hot-documents", _HOT_DOCUMENTS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_workbench_hot_documents(session)
    await _save_researcher_cache("researchers:workbench:hot-documents", items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/public-rank")
async def workbench_public_rank(
    sort_by: WorkbenchRankSortBy = "today",
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchPublicRankItem]]:
    """工作台 —— 公开排行榜。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = f"researchers:workbench:public-rank:{sort_by}"
    cached = await _load_researcher_cache(cache_name, _RANK_LIST_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_public_rankings(session, sort_by=sort_by)
    await _save_researcher_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/overview")
async def workbench_overview(
    sort_by: WorkbenchRankSortBy = "today",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[WorkbenchOverview]:
    """工作台 —— 首屏聚合数据。"""
    if not session:
        return ApiResponse(data=_empty_workbench_overview())
    return ApiResponse(data=await service.async_get_workbench_overview(session, user_id, sort_by=sort_by))


@router.get("/{researcher_id}")
async def get_researcher(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherDetail]:
    """查询研究员详情。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    cache_name = _detail_cache_name(researcher_id)
    cached = await _load_researcher_cache(cache_name, _DETAIL_ADAPTER)
    if cached is not None:
        return ApiResponse(data=cached)
    data = await service.async_get_researcher(session, researcher_id)
    await _save_researcher_cache(cache_name, data)
    return ApiResponse(data=data)


@router.post("")
async def create_researcher(
    payload: ResearcherCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherDetail]:
    """创建研究员"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_create_researcher(session, user_id, payload)
    await _invalidate_researcher_user_cache(user_id, data.researcher_id)
    return ApiResponse(data=data)


@router.patch("/{researcher_id}")
async def update_researcher(
    researcher_id: str,
    payload: ResearcherUpdateRequest,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherDetail]:
    """更新研究员"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_update_researcher(session, researcher_id, payload)
    await _invalidate_researcher_user_cache(None, researcher_id)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/duplicate")
async def duplicate_researcher(
    researcher_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherDetail]:
    """复制研究员。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_duplicate_researcher(session, researcher_id, user_id)
    await _invalidate_researcher_user_cache(user_id, data.researcher_id)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/publish")
async def publish_researcher(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherPublishRecord]:
    """发布研究员"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_publish(session, researcher_id)
    await _invalidate_researcher_user_cache(None, researcher_id)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/unpublish")
async def unpublish_researcher(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherPublishRecord]:
    """下架研究员"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_unpublish(session, researcher_id)
    await _invalidate_researcher_user_cache(None, researcher_id)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/test-chat")
async def test_chat(
    researcher_id: str,
    payload: ResearcherTestChatRequest,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherTestChatResponse]:
    """测试对话 —— 仅调用真实推理。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_test_chat(session=session, researcher_id=researcher_id, question=payload.question)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/hire")
async def hire_researcher(
    researcher_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[OperationResponse]:
    """雇佣研究员"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    await service.async_hire(session, user_id, researcher_id)
    await _invalidate_researcher_user_cache(user_id, researcher_id)
    return ApiResponse(data=OperationResponse(message="雇佣成功", resource_id=researcher_id))


@router.post("/{researcher_id}/dismiss")
async def dismiss_researcher(
    researcher_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[OperationResponse]:
    """解雇研究员"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    await service.async_dismiss(session, user_id, researcher_id)
    await _invalidate_researcher_user_cache(user_id, researcher_id)
    return ApiResponse(data=OperationResponse(message="已解雇研究员", resource_id=researcher_id))


@router.get("/{researcher_id}/scorecard")
async def get_scorecard(
    researcher_id: str,
    days: int = Query(30, ge=7, le=90),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[dict]:
    """研究员判断累积评分卡(近 N 天)。

    返回:
      - sample_size:已 T+1 评估的判断次数
      - accuracy:综合准确率
      - bias_breakdown:不同 bias 下的准确率
      - recent_logs:最近 5 条判断
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库不可用",
        )
    from collections import Counter
    from datetime import date, timedelta

    from sqlalchemy import select

    from app.models.researcher import ResearcherThesisLog

    cutoff = date.today() - timedelta(days=days)
    q = await session.execute(
        select(ResearcherThesisLog).where(
            ResearcherThesisLog.researcher_id == researcher_id,
            ResearcherThesisLog.trade_date >= cutoff,
        ).order_by(ResearcherThesisLog.trade_date.desc())
    )
    logs = list(q.scalars().all())
    evaluated = [l for l in logs if l.correctness != "pending"]
    sample_size = len(evaluated)
    correct = sum(1 for l in evaluated if l.correctness == "correct")
    bias_counter: Counter[str] = Counter(l.direction_call for l in evaluated)
    bias_correct: Counter[str] = Counter(
        l.direction_call for l in evaluated if l.correctness == "correct"
    )

    return ApiResponse(data={
        "researcher_id": researcher_id,
        "window_days": days,
        "total_logs": len(logs),
        "sample_size": sample_size,
        "accuracy": round(correct / sample_size, 3) if sample_size else 0.0,
        "bias_breakdown": [
            {
                "bias": b or "未明确",
                "count": cnt,
                "correct": bias_correct[b],
                "accuracy": round(bias_correct[b] / cnt, 3) if cnt else 0.0,
            }
            for b, cnt in bias_counter.most_common()
        ],
        "recent_logs": [
            {
                "trade_date": l.trade_date.isoformat(),
                "direction_call": l.direction_call,
                "correctness": l.correctness,
                "actual_result": l.actual_result,
            }
            for l in logs[:5]
        ],
    })
