"""
研究员路由

支持双模式：DB 就绪走 async_* 方法，否则 fallback 到 mock。
写操作（hire/dismiss/publish 等）在 DB 模式下需要 user_id。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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


@router.get("")
async def list_researchers(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherSummary]]:
    """查询所有研究员摘要（DB 查空时 fallback 到 mock）"""
    items = []
    if session:
        items = await service.async_list_researchers(session)
    if not items:
        items = service.list_researchers()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/market")
async def list_market(
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherMarketCard]]:
    """市场研究员列表（DB 查空时 fallback 到 mock）"""
    items, total = [], 0
    if session:
        items, total = await service.async_list_market(session, q=q, page=page, page_size=page_size)
    if not session or total == 0:
        items, total = service.list_market(q=q, page=page, page_size=page_size)
    return ApiResponse(data=ListResponse(items=items, total=total))


@router.get("/market/{researcher_id}")
async def market_detail(researcher_id: str) -> ApiResponse[ResearcherMarketDetail]:
    """市场研究员详情（暂仅 mock）"""
    return ApiResponse(data=service.get_market_detail(researcher_id))


@router.get("/mine")
async def list_mine(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[ResearcherMineItem]]:
    """我的研究员列表（DB 查空时 fallback 到 mock）"""
    items = []
    if session:
        items = await service.async_list_mine(session, user_id)
    if not items:
        items = service.list_mine()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/options/skills")
async def list_skill_options() -> ApiResponse[ListResponse[ResearcherOptionItem]]:
    """技能选项（暂仅 mock）"""
    items = service.list_skill_options()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/options/knowledge-bases")
async def list_knowledge_base_options() -> ApiResponse[ListResponse[ResearcherOptionItem]]:
    """知识库选项（暂仅 mock）"""
    items = service.list_knowledge_base_options()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/options/mcp-servers")
async def list_mcp_server_options() -> ApiResponse[ListResponse[ResearcherOptionItem]]:
    """MCP 服务器选项（暂仅 mock）"""
    items = service.list_mcp_server_options()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/hired")
async def workbench_hired(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchHiredResearcher]]:
    """工作台 —— 已雇佣研究员列表（DB 查空时 fallback 到 mock）"""
    items = []
    if session:
        items = await service.async_list_workbench_hired(session, user_id)
    if not items:
        items = service.list_workbench_hired()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/hot-documents")
async def workbench_hot_documents(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchHotDocument]]:
    """工作台 —— 热门文档（DB 优先，fallback 到 mock）"""
    if session:
        try:
            from sqlalchemy import select as sa_select
            from app.models.document import Document as DocModel
            stmt = sa_select(DocModel).order_by(DocModel.view_count.desc()).limit(6)
            doc_result = await session.execute(stmt)
            docs = doc_result.scalars().all()
            if docs:
                from app.repositories.researcher_repo import ResearcherRepository
                r_repo = ResearcherRepository(session)
                items = []
                for d in docs:
                    r = await r_repo.get_by_id(d.researcher_id)
                    items.append(WorkbenchHotDocument(
                        id=d.id, title=d.title, summary=d.summary,
                        researcher_name=r.name if r else "未知",
                        create_time=d.created_at,
                        view_count=d.view_count, comment_count=d.comment_count,
                    ))
                return ApiResponse(data=ListResponse(items=items, total=len(items)))
        except Exception:
            pass
    items = service.list_workbench_hot_documents()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/public-rank")
async def workbench_public_rank(
    sort_by: WorkbenchRankSortBy = "today",
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[WorkbenchPublicRankItem]]:
    """工作台 —— 公开排行榜（DB 优先，fallback 到 mock）"""
    if session:
        try:
            items = await service.async_list_public_rankings(session, sort_by=sort_by)
            if items:
                return ApiResponse(data=ListResponse(items=items, total=len(items)))
        except Exception:
            pass
    items = service.list_workbench_public_rankings(sort_by=sort_by)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/workbench/overview")
async def workbench_overview(
    sort_by: WorkbenchRankSortBy = "today",
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[WorkbenchOverview]:
    """工作台 —— 首屏聚合数据（DB 优先，fallback 到 mock）"""
    if session:
        try:
            data = await service.async_get_workbench_overview(session, user_id, sort_by=sort_by)
            if data.hired:  # DB 有数据则直接返回
                return ApiResponse(data=data)
        except Exception:
            pass
    return ApiResponse(data=service.get_workbench_overview(sort_by=sort_by))


@router.get("/{researcher_id}")
async def get_researcher(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherDetail]:
    """查询研究员详情（DB 查不到时 fallback 到 mock）"""
    data = None
    if session:
        try:
            data = await service.async_get_researcher(session, researcher_id)
        except HTTPException:
            data = None
    if data is None:
        data = service.get_researcher(researcher_id)
    return ApiResponse(data=data)


@router.post("")
async def create_researcher(
    payload: ResearcherCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherDetail]:
    """创建研究员"""
    if session:
        data = await service.async_create_researcher(session, user_id, payload)
    else:
        data = service.create_researcher(payload)
    return ApiResponse(data=data)


@router.patch("/{researcher_id}")
async def update_researcher(
    researcher_id: str,
    payload: ResearcherUpdateRequest,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherDetail]:
    """更新研究员"""
    if session:
        data = await service.async_update_researcher(session, researcher_id, payload)
    else:
        data = service.update_researcher(researcher_id, payload)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/duplicate")
async def duplicate_researcher(researcher_id: str) -> ApiResponse[ResearcherDetail]:
    """复制研究员（暂仅 mock）"""
    return ApiResponse(data=service.duplicate_researcher(researcher_id))


@router.post("/{researcher_id}/publish")
async def publish_researcher(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherPublishRecord]:
    """发布研究员"""
    if session:
        data = await service.async_publish(session, researcher_id)
    else:
        data = service.publish_researcher(researcher_id)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/unpublish")
async def unpublish_researcher(
    researcher_id: str,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ResearcherPublishRecord]:
    """下架研究员"""
    if session:
        data = await service.async_unpublish(session, researcher_id)
    else:
        data = service.unpublish_researcher(researcher_id)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/test-chat")
async def test_chat(
    researcher_id: str,
    payload: ResearcherTestChatRequest,
) -> ApiResponse[ResearcherTestChatResponse]:
    """测试对话 —— LLM 已配置时调用真实推理，否则返回 mock"""
    data = await service.test_chat(researcher_id=researcher_id, question=payload.question)
    return ApiResponse(data=data)


@router.post("/{researcher_id}/test-chat/stream")
async def test_chat_stream(
    researcher_id: str,
    payload: ResearcherTestChatRequest,
) -> StreamingResponse:
    """流式测试对话 —— SSE 逐 token 返回

    前端通过 EventSource 或 fetch + ReadableStream 消费。
    每个 SSE 事件格式：data: {"token": "..."}
    结束标记：data: [DONE]
    """
    from app.integrations.llm.client import LLMMessage as Msg, get_llm_client

    detail = service.get_researcher(researcher_id)

    # 构建 system prompt
    system_prompt = (
        f"你是一名名叫「{detail.name}」的 AI 研究员。\n"
        f"职位：{detail.title}\n"
        f"风格：{detail.style}\n"
        f"简介：{detail.description}\n\n"
    )
    if detail.prompt:
        system_prompt += f"特殊指令：{detail.prompt}\n\n"
    system_prompt += "请基于以上角色设定回答用户的问题。回复应专业、有条理。"

    messages = [
        Msg(role="system", content=system_prompt),
        Msg(role="user", content=payload.question),
    ]

    llm = get_llm_client()

    async def _event_generator() -> AsyncIterator[str]:
        """SSE 事件生成器"""
        async for token in llm.chat_stream(messages):
            yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{researcher_id}/hire")
async def hire_researcher(
    researcher_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[OperationResponse]:
    """雇佣研究员"""
    if session:
        await service.async_hire(session, user_id, researcher_id)
    else:
        service.set_status(researcher_id, "active")
    return ApiResponse(data=OperationResponse(message="雇佣成功", resource_id=researcher_id))


@router.post("/{researcher_id}/dismiss")
async def dismiss_researcher(
    researcher_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[OperationResponse]:
    """解雇研究员"""
    if session:
        await service.async_dismiss(session, user_id, researcher_id)
    else:
        service.set_status(researcher_id, "dismissed")
    return ApiResponse(data=OperationResponse(message="已解雇研究员", resource_id=researcher_id))
