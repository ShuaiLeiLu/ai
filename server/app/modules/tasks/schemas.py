from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from app.schemas.common import SchemaModel

ScheduleType = Literal["one_time", "interval", "cron"]
TaskStatus = Literal["DRAFT", "ACTIVE", "RUNNING", "SUCCESS", "FAILED", "PAUSED", "DELETED"]
RunResultType = Literal["none", "document", "message"]
RunLogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]

DYNAMIC_VARIABLE_HINTS: tuple[str, ...] = (
    "{{date}}",
    "{{lastDate}}",
    "{{nextDate}}",
    "{{lastTradeDate}}",
    "{{nextTradeDate}}",
)


class TaskConfigBase(SchemaModel):
    title: str = Field(min_length=1, max_length=100)
    researcher_id: str = Field(min_length=1, max_length=64)
    schedule_type: ScheduleType
    schedule_config: dict[str, Any] = Field(default_factory=dict)
    trade_day_only: bool = False
    force_output_document: bool = False
    description: str = Field(default="", max_length=4000)
    prompt_template: str = Field(default="", max_length=8000)


class TaskSummary(TaskConfigBase):
    task_id: str
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    last_run_at: datetime | None = None
    dynamic_variable_hints: list[str] = Field(default_factory=lambda: list(DYNAMIC_VARIABLE_HINTS))


class TaskCreateRequest(TaskConfigBase):
    pass


class TaskUpdateRequest(SchemaModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    researcher_id: str | None = Field(default=None, min_length=1, max_length=64)
    schedule_type: ScheduleType | None = None
    schedule_config: dict[str, Any] | None = None
    trade_day_only: bool | None = None
    force_output_document: bool | None = None
    description: str | None = Field(default=None, max_length=4000)
    prompt_template: str | None = Field(default=None, max_length=8000)


class TaskRunRecord(SchemaModel):
    run_id: str
    task_id: str
    trigger_time: datetime
    start_time: datetime
    end_time: datetime | None = None
    status: TaskStatus
    result_type: RunResultType = "none"
    error_message: str | None = None


class TaskRunLog(SchemaModel):
    log_id: str
    run_id: str
    level: RunLogLevel
    content: str
    create_time: datetime
