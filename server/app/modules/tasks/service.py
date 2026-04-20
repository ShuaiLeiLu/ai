from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status

from app.modules.tasks.schemas import (
    TaskCreateRequest,
    TaskRunLog,
    TaskRunRecord,
    TaskStatus,
    TaskSummary,
    TaskUpdateRequest,
)


class TaskService:
    """任务编排领域服务。

    当前执行逻辑是模拟执行，后续会由 Celery worker 真正消费任务。
    """

    def __init__(self) -> None:
        now = datetime.now(tz=UTC)
        self._tasks: dict[str, TaskSummary] = {
            "t_preopen_1": TaskSummary(
                task_id="t_preopen_1",
                title="盘前速览生成",
                researcher_id="r_alpha",
                schedule_type="cron",
                schedule_config={"expr": "0 8 * * 1-5"},
                trade_day_only=True,
                force_output_document=True,
                description="交易日盘前自动生成市场速览文档。",
                prompt_template="请基于{{lastTradeDate}}到{{date}}市场数据生成盘前简报。",
                status="ACTIVE",
                last_run_at=now - timedelta(hours=8),
                created_at=now - timedelta(days=7),
                updated_at=now - timedelta(hours=8),
            )
        }
        # 运行记录和日志独立维护，后续可平滑迁移到独立表。
        self._runs: list[TaskRunRecord] = []
        self._run_logs: dict[str, list[TaskRunLog]] = {}

    def list_tasks(self, *, status_value: TaskStatus | None = None, schedule_type: str | None = None) -> list[TaskSummary]:
        # 过滤逻辑：
        # 1) 默认不返回已删除任务（软删除）；
        # 2) 如显式传入 status，则按状态精确过滤。
        items = list(self._tasks.values())
        if status_value:
            items = [item for item in items if item.status == status_value]
        else:
            items = [item for item in items if item.status != "DELETED"]
        if schedule_type:
            items = [item for item in items if item.schedule_type == schedule_type]
        return items

    def create_task(self, payload: TaskCreateRequest) -> TaskSummary:
        task_id = f"t_{uuid4().hex[:10]}"
        now = datetime.now(tz=UTC)
        task = TaskSummary(
            task_id=task_id,
            title=payload.title,
            researcher_id=payload.researcher_id,
            schedule_type=payload.schedule_type,
            schedule_config=payload.schedule_config,
            trade_day_only=payload.trade_day_only,
            force_output_document=payload.force_output_document,
            description=payload.description,
            prompt_template=payload.prompt_template,
            status="DRAFT",
            created_at=now,
            updated_at=now,
            last_run_at=None,
        )
        self._tasks[task_id] = task
        return task

    def update_task(self, task_id: str, payload: TaskUpdateRequest) -> TaskSummary:
        task = self._get_task_or_404(task_id)
        if task.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法更新")

        changed = task.model_dump()
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            changed[key] = value
        changed["updated_at"] = datetime.now(tz=UTC)
        updated = TaskSummary(**changed)
        self._tasks[task_id] = updated
        return updated

    def delete_task(self, task_id: str) -> TaskSummary:
        task = self._get_task_or_404(task_id)
        if task.status == "DELETED":
            return task
        changed = task.model_dump()
        changed["status"] = "DELETED"
        changed["updated_at"] = datetime.now(tz=UTC)
        deleted = TaskSummary(**changed)
        self._tasks[task_id] = deleted
        return deleted

    def activate_task(self, task_id: str) -> TaskSummary:
        task = self._get_task_or_404(task_id)
        # 状态流转：DRAFT/PAUSED/SUCCESS/FAILED -> ACTIVE
        if task.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法启用")
        if task.status == "RUNNING":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务运行中，无法重复启用")
        return self._set_task_status(task_id, "ACTIVE")

    def pause_task(self, task_id: str) -> TaskSummary:
        task = self._get_task_or_404(task_id)
        # 状态流转：ACTIVE/RUNNING -> PAUSED
        if task.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法暂停")
        if task.status == "DRAFT":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="草稿任务无需暂停")
        return self._set_task_status(task_id, "PAUSED")

    def run_task(self, task_id: str) -> TaskRunRecord:
        task = self._get_task_or_404(task_id)
        if task.status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法执行")
        if task.status == "PAUSED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已暂停，请先启用再执行")

        now = datetime.now(tz=UTC)
        self._set_task_status(task_id, "RUNNING", now)

        # 模拟执行成功/失败，便于前端联调不同状态。
        is_fail = "[FAIL]" in task.prompt_template.upper()
        end_time = now + timedelta(seconds=1)
        run_status: TaskStatus = "FAILED" if is_fail else "SUCCESS"
        error_message = "模拟执行失败，请检查 prompt_template" if is_fail else None

        run = TaskRunRecord(
            run_id=f"tr_{uuid4().hex[:12]}",
            task_id=task_id,
            trigger_time=now,
            start_time=now,
            end_time=end_time,
            status=run_status,
            result_type="document" if task.force_output_document else "message",
            error_message=error_message,
        )
        self._runs.insert(0, run)
        self._run_logs[run.run_id] = [
            TaskRunLog(
                log_id=f"log_{uuid4().hex[:10]}",
                run_id=run.run_id,
                level="INFO",
                content=f"任务触发：{task.title}",
                create_time=now,
            ),
            TaskRunLog(
                log_id=f"log_{uuid4().hex[:10]}",
                run_id=run.run_id,
                level="INFO",
                content="执行中：正在生成输出内容",
                create_time=now + timedelta(milliseconds=400),
            ),
            TaskRunLog(
                log_id=f"log_{uuid4().hex[:10]}",
                run_id=run.run_id,
                level="ERROR" if is_fail else "INFO",
                content=error_message or "执行完成：任务成功结束",
                create_time=end_time,
            ),
        ]
        changed = self._get_task_or_404(task_id).model_dump()
        changed["last_run_at"] = end_time
        changed["status"] = run_status
        changed["updated_at"] = end_time
        self._tasks[task_id] = TaskSummary(**changed)
        return run

    def list_runs(self, task_id: str | None = None) -> list[TaskRunRecord]:
        if task_id:
            return [item for item in self._runs if item.task_id == task_id]
        return self._runs

    def list_task_runs(self, task_id: str) -> list[TaskRunRecord]:
        self._get_task_or_404(task_id)
        return [item for item in self._runs if item.task_id == task_id]

    def list_run_logs(self, run_id: str) -> list[TaskRunLog]:
        if run_id not in self._run_logs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在或暂无日志")
        return self._run_logs[run_id]

    def _get_task_or_404(self, task_id: str) -> TaskSummary:
        task = self._tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        return task

    def _set_task_status(
        self, task_id: str, status_value: TaskStatus, updated_at: datetime | None = None
    ) -> TaskSummary:
        task = self._get_task_or_404(task_id)
        changed = task.model_dump()
        changed["status"] = status_value
        changed["updated_at"] = updated_at or datetime.now(tz=UTC)
        updated = TaskSummary(**changed)
        self._tasks[task_id] = updated
        return updated
