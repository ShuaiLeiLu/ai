from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router_factory import create_api_v1_router
from app.core.config import Settings, get_settings
from app.core.container import get_container
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.modules.module_registry import ModuleRegistry


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    configure_logging()
    container = get_container()
    await container.startup()

    # 启动策略调度引擎（进程内，不依赖 Celery/Redis）
    from app.engine.scheduler import start_scheduler, stop_scheduler
    start_scheduler(container.database, container.redis)

    yield

    stop_scheduler()
    await container.shutdown()


def configure_middlewares(app: FastAPI, settings: Settings) -> None:
    # allow_credentials 不能和 allow_origins=["*"] 同时使用
    allow_all = "*" in settings.cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=not allow_all,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def configure_routes(
    app: FastAPI,
    settings: Settings,
    module_registry: ModuleRegistry | None = None,
) -> None:
    api_v1_router = create_api_v1_router(module_registry=module_registry)
    app.include_router(api_v1_router, prefix=settings.api_v1_prefix)


def create_app(
    settings: Settings | None = None,
    module_registry: ModuleRegistry | None = None,
) -> FastAPI:
    """统一构建 FastAPI 应用，集中管理装配流程。"""

    app_settings = settings or get_settings()
    app = FastAPI(
        title=app_settings.app_name,
        version=app_settings.app_version,
        debug=app_settings.debug,
        lifespan=app_lifespan,
    )

    configure_middlewares(app, app_settings)
    configure_routes(app, app_settings, module_registry=module_registry)
    register_exception_handlers(app)
    return app
