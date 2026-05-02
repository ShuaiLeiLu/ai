from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.security import get_current_user_id
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
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskSummary]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    items = await service.list_tasks(session, user_id=user_id, status_value=status, schedule_type=schedule_type)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.post("")
async def create_task(
    payload: TaskCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    return ApiResponse(data=await service.create_task(session, user_id, payload))


@router.get("/runs")
async def list_runs(
    task_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskRunRecord]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    items = await service.list_runs(session, user_id=user_id, task_id=task_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/runs/{run_id}/logs")
async def list_run_logs(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskRunLog]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    items = await service.list_run_logs(session, user_id, run_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.patch("/{task_id}")
async def update_task(
    task_id: str,
    payload: TaskUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    return ApiResponse(data=await service.update_task(session, user_id, task_id, payload))


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    return ApiResponse(data=await service.delete_task(session, user_id, task_id))


@router.post("/{task_id}/activate")
async def activate_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    return ApiResponse(data=await service.activate_task(session, user_id, task_id))


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    return ApiResponse(data=await service.pause_task(session, user_id, task_id))


@router.post("/{task_id}/run")
async def run_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskRunRecord]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    return ApiResponse(data=await service.run_task(session, user_id, task_id))


@router.get("/{task_id}/runs")
async def list_task_runs(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskRunRecord]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    items = await service.list_task_runs(session, user_id, task_id)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
