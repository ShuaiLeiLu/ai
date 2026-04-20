from __future__ import annotations

from app.modules.auth.router import router
from app.modules.base_module import ModuleDefinition


async def _startup() -> None:
    """Reserved hook for auth module bootstrap (cache warmup, key preload, etc.)."""


module = ModuleDefinition(name="auth", router=router, startup=_startup)
