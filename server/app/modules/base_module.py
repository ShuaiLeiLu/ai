"""Legacy module protocol and factory utilities.

.. note::

   The *canonical* module registration mechanism is
   :mod:`app.modules.module_registry` (``ModuleSpec`` / ``get_default_module_registry``).
   This file is retained for backward compatibility with per-module ``module.py``
   descriptors (e.g. ``auth/module.py``, ``system/module.py``) and the related
   factory bootstrap tests.  New modules should be added to
   ``module_registry.get_default_module_registry()`` only.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter

StartupHook = Callable[[], Awaitable[None] | None]


class AppModule(Protocol):
    """Contract for a module that can be registered by the module factory."""

    name: str
    router: APIRouter
    startup: StartupHook | None


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    """Default concrete implementation of the module contract."""

    name: str
    router: APIRouter
    startup: StartupHook | None = None


class ModuleRegistry:
    """In-memory module registry with duplicate-name protection."""

    def __init__(self) -> None:
        self._modules: dict[str, AppModule] = {}

    def register(self, module: AppModule) -> None:
        if module.name in self._modules:
            raise ValueError(f"Module '{module.name}' is already registered")
        self._modules[module.name] = module

    def register_many(self, modules: Iterable[AppModule]) -> None:
        for module in modules:
            self.register(module)

    def get(self, name: str) -> AppModule:
        return self._modules[name]

    def has(self, name: str) -> bool:
        return name in self._modules

    def list(self) -> list[AppModule]:
        return [self._modules[name] for name in sorted(self._modules)]


class ModuleFactory:
    """Build API routers and lifecycle hooks from a module registry."""

    def __init__(self, registry: ModuleRegistry) -> None:
        self.registry = registry

    def build_router(self) -> APIRouter:
        api_router = APIRouter()
        for module in self.registry.list():
            api_router.include_router(module.router)
        return api_router

    def startup_hooks(self) -> list[StartupHook]:
        hooks: list[StartupHook] = []
        for module in self.registry.list():
            if module.startup is not None:
                hooks.append(module.startup)
        return hooks


def create_default_registry() -> ModuleRegistry:
    """Register built-in modules managed by the factory."""

    from app.modules.auth.module import module as auth_module
    from app.modules.system.module import module as system_module

    registry = ModuleRegistry()
    registry.register_many([system_module, auth_module])
    return registry


def build_api_router(registry: ModuleRegistry | None = None) -> APIRouter:
    active_registry = registry or create_default_registry()
    return ModuleFactory(active_registry).build_router()


def collect_startup_hooks(registry: ModuleRegistry | None = None) -> list[StartupHook]:
    active_registry = registry or create_default_registry()
    return ModuleFactory(active_registry).startup_hooks()
