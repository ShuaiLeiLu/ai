from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.container import get_container
from app.core.security import get_current_user_id
from app.modules.ecosystem.schemas import KnowledgeBaseItem, McpServerItem, SkillItem
from app.modules.ecosystem.service import EcosystemService
from app.modules.page_cache import load_cached, save_cached
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])
service = EcosystemService()
_CACHE_TTL_SECONDS = 300
_KNOWLEDGE_BASES_ADAPTER = TypeAdapter(list[KnowledgeBaseItem])
_SKILLS_ADAPTER = TypeAdapter(list[SkillItem])
_MCP_SERVERS_ADAPTER = TypeAdapter(list[McpServerItem])


async def _load_ecosystem_cache(name: str, adapter: TypeAdapter):
    try:
        redis = get_container().redis.get_client()
        return await load_cached(redis, name, adapter)
    except Exception:
        return None


async def _save_ecosystem_cache(name: str, data: object) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, name, data, ttl_seconds=_CACHE_TTL_SECONDS)
    except Exception:
        return


@router.get("/knowledge-bases")
async def list_knowledge_bases(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[KnowledgeBaseItem]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = f"ecosystem:knowledge-bases:{user_id}"
    cached = await _load_ecosystem_cache(cache_name, _KNOWLEDGE_BASES_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_knowledge_bases(session, user_id)
    await _save_ecosystem_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/skills")
async def list_skills(
    installed: bool | None = None,
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[SkillItem]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = f"ecosystem:skills:installed={installed if installed is not None else 'all'}"
    cached = await _load_ecosystem_cache(cache_name, _SKILLS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_skills(session)
    if installed is not None:
        items = [item for item in items if item.installed is installed]
    await _save_ecosystem_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/mcp-servers")
async def list_mcp_servers(
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[McpServerItem]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cached = await _load_ecosystem_cache("ecosystem:mcp-servers", _MCP_SERVERS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.async_list_mcp_servers(session)
    await _save_ecosystem_cache("ecosystem:mcp-servers", items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
