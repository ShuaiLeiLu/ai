"""
研究员路由

优先返回真实数据库数据。
未接入真实数据源时，仅返回空结果或明确错误。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.security import get_current_user_id
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
    items = await service.async_list_researchers(session) if session else []
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/market")
async def list_market(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherMarketCard]]:
    """市场研究员列表。"""
    items, total = await service.async_list_market(session, q=q, page=page, page_size=page_size) if session else ([], 0)
    return ApiResponse(data=ListResponse(items=items, total=total))


@router.get("/market/{researcher_id}")
async def market_detail(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherMarketDetail]:
    """市场研究员详情。"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    return ApiResponse(data=await service.async_get_market_detail(session, researcher_id))


@router.get("/mine")
async def list_mine(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherMineItem]]:
    """我的研究员列表。"""
    items = await service.async_list_mine(session, user_id) if session else []
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
    items = await service.async_list_workbench_hired(session, user_id) if session else []
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/hot-documents")
async def workbench_hot_documents(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchHotDocument]]:
    """工作台 —— 热门文档。"""
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))

    items = await service.async_list_workbench_hot_documents(session)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/public-rank")
async def workbench_public_rank(
    sort_by: WorkbenchRankSortBy = "today",
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchPublicRankItem]]:
    """工作台 —— 公开排行榜。"""
    items = await service.async_list_public_rankings(session, sort_by=sort_by) if session else []
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
    return ApiResponse(data=await service.async_get_researcher(session, researcher_id))


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
    return ApiResponse(data=await service.async_duplicate_researcher(session, researcher_id, user_id))


@router.post("/{researcher_id}/publish")
async def publish_researcher(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherPublishRecord]:
    """发布研究员"""
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.async_publish(session, researcher_id)
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
    return ApiResponse(data=OperationResponse(message="已解雇研究员", resource_id=researcher_id))
