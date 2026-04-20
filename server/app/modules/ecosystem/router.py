from __future__ import annotations

from fastapi import APIRouter

from app.modules.ecosystem.schemas import KnowledgeBaseItem, McpServerItem, SkillItem
from app.modules.ecosystem.service import EcosystemService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/ecosystem", tags=["ecosystem"])
service = EcosystemService()


@router.get("/knowledge-bases")
async def list_knowledge_bases() -> ApiResponse[ListResponse[KnowledgeBaseItem]]:
    items = service.list_knowledge_bases()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/skills")
async def list_skills(installed: bool | None = None) -> ApiResponse[ListResponse[SkillItem]]:
    items = service.list_skills(installed=installed)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/mcp-servers")
async def list_mcp_servers() -> ApiResponse[ListResponse[McpServerItem]]:
    items = service.list_mcp_servers()
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
