from __future__ import annotations

from app.core.celery_app import celery_app
from app.tasks.base import LoggedTask


@celery_app.task(base=LoggedTask, name="maintenance.ping")
def ping() -> str:
    return "pong"
