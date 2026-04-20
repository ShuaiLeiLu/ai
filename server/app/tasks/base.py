from __future__ import annotations

from celery import Task


class LoggedTask(Task):
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_kwargs = {"max_retries": 3}
