from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_optional_session
from app.core.container import get_container
from app.core.security import get_current_user_id
from app.modules.page_cache import delete_cached, load_cached, save_cached
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
_CACHE_TTL_SECONDS = 60
_TASKS_ADAPTER = TypeAdapter(list[TaskSummary])
_RUNS_ADAPTER = TypeAdapter(list[TaskRunRecord])
_LOGS_ADAPTER = TypeAdapter(list[TaskRunLog])


async def _load_task_cache(name: str, adapter: TypeAdapter):
    try:
        redis = get_container().redis.get_client()
        return await load_cached(redis, name, adapter)
    except Exception:
        return None


async def _save_task_cache(name: str, data: object) -> None:
    try:
        redis = get_container().redis.get_client()
        await save_cached(redis, name, data, ttl_seconds=_CACHE_TTL_SECONDS)
    except Exception:
        return


async def _delete_task_cache(*names: str) -> None:
    try:
        redis = get_container().redis.get_client()
        for name in names:
            await delete_cached(redis, name)
    except Exception:
        return


def _tasks_cache_name(user_id: str, status: TaskStatus | None, schedule_type: ScheduleType | None) -> str:
    return f"tasks:list:{user_id}:status={status or 'all'}:schedule={schedule_type or 'all'}"


def _runs_cache_name(user_id: str, task_id: str | None) -> str:
    return f"tasks:runs:{user_id}:task={task_id or 'all'}"


def _task_runs_cache_name(user_id: str, task_id: str) -> str:
    return f"tasks:task-runs:{user_id}:{task_id}"


def _logs_cache_name(user_id: str, run_id: str) -> str:
    return f"tasks:logs:{user_id}:{run_id}"


async def _invalidate_task_user_cache(user_id: str, task_id: str | None = None) -> None:
    names = [_tasks_cache_name(user_id, None, None), _runs_cache_name(user_id, None)]
    if task_id:
        names.append(_task_runs_cache_name(user_id, task_id))
    await _delete_task_cache(*names)


@router.get("")
async def list_tasks(
    status: TaskStatus | None = None,
    schedule_type: ScheduleType | None = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskSummary]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _tasks_cache_name(user_id, status, schedule_type)
    cached = await _load_task_cache(cache_name, _TASKS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.list_tasks(session, user_id=user_id, status_value=status, schedule_type=schedule_type)
    await _save_task_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.post("")
async def create_task(
    payload: TaskCreateRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.create_task(session, user_id, payload)
    await _invalidate_task_user_cache(user_id, data.task_id)
    return ApiResponse(data=data)


@router.get("/runs")
async def list_runs(
    task_id: str | None = None,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskRunRecord]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _runs_cache_name(user_id, task_id)
    cached = await _load_task_cache(cache_name, _RUNS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.list_runs(session, user_id=user_id, task_id=task_id)
    await _save_task_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))


@router.get("/runs/{run_id}/logs")
async def list_run_logs(
    run_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskRunLog]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _logs_cache_name(user_id, run_id)
    cached = await _load_task_cache(cache_name, _LOGS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.list_run_logs(session, user_id, run_id)
    await _save_task_cache(cache_name, items)
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
    data = await service.update_task(session, user_id, task_id, payload)
    await _invalidate_task_user_cache(user_id, task_id)
    return ApiResponse(data=data)


@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.delete_task(session, user_id, task_id)
    await _invalidate_task_user_cache(user_id, task_id)
    return ApiResponse(data=data)


@router.post("/{task_id}/activate")
async def activate_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.activate_task(session, user_id, task_id)
    await _invalidate_task_user_cache(user_id, task_id)
    return ApiResponse(data=data)


@router.post("/{task_id}/pause")
async def pause_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskSummary]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.pause_task(session, user_id, task_id)
    await _invalidate_task_user_cache(user_id, task_id)
    return ApiResponse(data=data)


@router.post("/{task_id}/run")
async def run_task(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[TaskRunRecord]:
    if not session:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="数据库不可用")
    data = await service.run_task(session, user_id, task_id)
    await _invalidate_task_user_cache(user_id, task_id)
    return ApiResponse(data=data)


@router.get("/{task_id}/runs")
async def list_task_runs(
    task_id: str,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession | None = Depends(get_optional_session),
) -> ApiResponse[ListResponse[TaskRunRecord]]:
    if not session:
        return ApiResponse(data=ListResponse(items=[], total=0))
    cache_name = _task_runs_cache_name(user_id, task_id)
    cached = await _load_task_cache(cache_name, _RUNS_ADAPTER)
    if cached is not None:
        return ApiResponse(data=ListResponse(items=cached, total=len(cached)))
    items = await service.list_task_runs(session, user_id, task_id)
    await _save_task_cache(cache_name, items)
    return ApiResponse(data=ListResponse(items=items, total=len(items)))
