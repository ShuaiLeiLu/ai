from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import Settings

if TYPE_CHECKING:
    from celery import Celery


class CeleryFactory:
    """Builds and keeps the Celery app instance."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._app: Celery | None = None

    def get_app(self) -> Celery:
        if self._app is None:
            from celery import Celery

            app = Celery(
                "cyber_invest",
                broker=self._settings.celery_broker_url,
                backend=self._settings.celery_result_backend,
                include=[
                    "app.tasks.maintenance",
                    "app.tasks.trading_tasks",
                    "app.tasks.researcher_tasks",
                    "app.tasks.news_tasks",
                ],
            )
            app.conf.update(
                task_track_started=True,
                task_serializer="json",
                result_serializer="json",
                accept_content=["json"],
                timezone="Asia/Shanghai",
                enable_utc=False,
            )
            self._app = app
        return self._app

    async def shutdown(self) -> None:
        if self._app is None:
            return
        close_fn = getattr(self._app, "close", None)
        if callable(close_fn):
            close_fn()
        self._app = None
