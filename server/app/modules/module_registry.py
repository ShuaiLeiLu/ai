from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from importlib import import_module

from fastapi import APIRouter


@dataclass(frozen=True, slots=True)
class ModuleSpec:
    """描述一个可装配模块。"""

    name: str
    router_module: str
    router_attr: str = "router"
    enabled: bool = True


class ModuleRegistry:
    """按清单管理并加载模块路由。"""

    def __init__(self, specs: Sequence[ModuleSpec] | None = None) -> None:
        self._specs: list[ModuleSpec] = list(specs or [])

    def register(self, spec: ModuleSpec) -> None:
        self._specs.append(spec)

    def extend(self, specs: Iterable[ModuleSpec]) -> None:
        self._specs.extend(specs)

    def enabled_specs(self) -> list[ModuleSpec]:
        return [spec for spec in self._specs if spec.enabled]

    def iter_routers(self) -> Iterable[APIRouter]:
        for spec in self.enabled_specs():
            yield self._load_router(spec)

    @staticmethod
    def _load_router(spec: ModuleSpec) -> APIRouter:
        module = import_module(spec.router_module)
        router = getattr(module, spec.router_attr, None)
        if not isinstance(router, APIRouter):
            raise TypeError(
                f"Module '{spec.name}' router '{spec.router_module}.{spec.router_attr}' "
                "must be an instance of APIRouter."
            )
        return router


def get_default_module_registry() -> ModuleRegistry:
    """默认模块清单：新增模块时只需在这里注册。"""

    return ModuleRegistry(
        specs=[
            ModuleSpec(name="system", router_module="app.modules.system.router"),
            ModuleSpec(name="auth", router_module="app.modules.auth.router"),
            ModuleSpec(name="researchers", router_module="app.modules.researchers.router"),
            ModuleSpec(name="documents", router_module="app.modules.documents.router"),
            ModuleSpec(name="tasks", router_module="app.modules.tasks.router"),
            ModuleSpec(name="news", router_module="app.modules.news.router"),
            ModuleSpec(name="news_analysis", router_module="app.modules.news_analysis.router"),
            ModuleSpec(name="market_data", router_module="app.modules.market_data.router"),
            ModuleSpec(name="preopen", router_module="app.modules.preopen.router"),
            ModuleSpec(name="community", router_module="app.modules.community.router"),
            ModuleSpec(name="notes", router_module="app.modules.notes.router"),
            ModuleSpec(name="webhooks", router_module="app.modules.webhooks.router"),
            ModuleSpec(name="billing", router_module="app.modules.billing.router"),
            ModuleSpec(name="ecosystem", router_module="app.modules.ecosystem.router"),
            ModuleSpec(name="trading", router_module="app.modules.trading.router"),
        ]
    )
