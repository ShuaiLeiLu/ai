from __future__ import annotations

from fastapi import APIRouter

from app.modules.module_registry import ModuleRegistry, get_default_module_registry


def create_api_v1_router(module_registry: ModuleRegistry | None = None) -> APIRouter:
    """按模块注册器组装 API v1 路由。"""

    registry = module_registry or get_default_module_registry()
    api_router = APIRouter()
    for module_router in registry.iter_routers():
        api_router.include_router(module_router)
    return api_router
