from __future__ import annotations

from fastapi import APIRouter

from app.modules.tasks.schemas import (
    ScheduleType,
    TaskCreateRequest,
    TaskRunLog,
    TaskRunRecord,
    TaskStatus,
    TaskSummary,
    TaskUpdateRequest,
)
from app.modules.tasks.service import TaskService
from app.schemas.common import ApiResponse, ListResponse

router = APIRouter(prefix="/tasks", tags=["tasks"])
service = TaskService()


@router.get("")
async def list_tasks(
    status: TaskStatus | None = None,
    schedule_type: ScheduleType | None = None,
) -> ApiResponse[ListResponse[TaskSummary]]:
    items = service.list_tasks(status_value=status, schedule_type=schedule_type)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.post("")
async def create_task(payload: TaskCreateRequest) -> ApiResponse[TaskSummary]:
    return ApiResponse(data=service.create_task(payload))


@router.get("/runs")
async def list_runs(task_id: str | None = None) -> ApiResponse[ListResponse[TaskRunRecord]]:
    items = service.list_runs(task_id=task_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/runs/{run_id}/logs")
async def list_run_logs(run_id: str) -> ApiResponse[ListResponse[TaskRunLog]]:
    items = service.list_run_logs(run_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.patch("/{task_id}")
async def update_task(task_id: str, payload: TaskUpdateRequest) -> ApiResponse[TaskSummary]:
    return ApiResponse(data=service.update_task(task_id, payload))


@router.delete("/{task_id}")
async def delete_task(task_id: str) -> ApiResponse[TaskSummary]:
    return ApiResponse(data=service.delete_task(task_id))


@router.post("/{task_id}/activate")
async def activate_task(task_id: str) -> ApiResponse[TaskSummary]:
    return ApiResponse(data=service.activate_task(task_id))


@router.post("/{task_id}/pause")
async def pause_task(task_id: str) -> ApiResponse[TaskSummary]:
    return ApiResponse(data=service.pause_task(task_id))


@router.post("/{task_id}/run")
async def run_task(task_id: str) -> ApiResponse[TaskRunRecord]:
    return ApiResponse(data=service.run_task(task_id))


@router.get("/{task_id}/runs")
async def list_task_runs(task_id: str) -> ApiResponse[ListResponse[TaskRunRecord]]:
    items = service.list_task_runs(task_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
