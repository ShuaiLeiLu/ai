from __future__ import annotations

from datetime import UTC, datetime

from app.core.config import get_settings
from app.modules.system.schemas import HealthResponse

settings = get_settings()


class SystemService:
    def get_health(self) -> HealthResponse:
        return HealthResponse(
            status="ok",
            service=settings.app_name,
            version=settings.app_version,
            environment=settings.app_env,
            timestamp=datetime.now(tz=UTC),
        )
