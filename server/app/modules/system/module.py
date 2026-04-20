from __future__ import annotations

from app.modules.base_module import ModuleDefinition
from app.modules.system.router import router

module = ModuleDefinition(name="system", router=router)
