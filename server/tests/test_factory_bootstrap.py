from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.base_module import collect_startup_hooks, create_default_registry


def test_registry_can_resolve_system_module() -> None:
    registry = create_default_registry()

    assert registry.has("system")
    assert registry.get("system").name == "system"


def test_factory_bootstrap_exposes_health_route() -> None:
    registry = create_default_registry()
    app = FastAPI()

    from app.modules.base_module import ModuleFactory

    app.include_router(ModuleFactory(registry).build_router(), prefix="/api/v1")

    client = TestClient(app)
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_collect_startup_hooks_contains_auth_hook_only() -> None:
    hooks = collect_startup_hooks()

    assert len(hooks) == 1
    assert hooks[0].__name__ == "_startup"
