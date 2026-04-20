from __future__ import annotations

from fastapi import APIRouter

from app.modules.system.service import SystemService

router = APIRouter(tags=["system"])
service = SystemService()


@router.get("/health")
async def health_check():
    return service.get_health()


@router.get("/live")
async def live_check():
    return {"status": "alive"}
