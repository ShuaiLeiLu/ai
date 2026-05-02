from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.akshare.client import list_recent_trade_dates, run_sync
from app.integrations.llm.client import LLMMessage, get_llm_client
from app.models.document import Document
from app.models.researcher import Researcher
from app.models.researcher import ResearcherHire
from app.models.task import OrchestrationTask, OrchestrationTaskRun, OrchestrationTaskRunLog
from app.modules.tasks.schemas import (
    TaskCreateRequest,
    TaskLifecycleStatus,
    TaskRunLog,
    TaskRunRecord,
    TaskRunStatus,
    TaskStatus,
    TaskSummary,
    TaskUpdateRequest,
)


class TaskService:
    """任务编排领域服务：持久化任务、运行记录、日志和输出文档。"""

    async def list_tasks(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        status_value: TaskStatus | None = None,
        schedule_type: str | None = None,
    ) -> list[TaskSummary]:
        stmt = select(OrchestrationTask).where(OrchestrationTask.owner_id == user_id)
        if status_value:
            lifecycle_status = self._coerce_lifecycle_status(status_value)
            if lifecycle_status:
                stmt = stmt.where(OrchestrationTask.lifecycle_status == lifecycle_status)
            else:
                stmt = stmt.where(OrchestrationTask.last_run_status == status_value)
        else:
            stmt = stmt.where(OrchestrationTask.lifecycle_status != "DELETED")
        if schedule_type:
            stmt = stmt.where(OrchestrationTask.schedule_type == schedule_type)
        stmt = stmt.order_by(OrchestrationTask.updated_at.desc())
        result = await session.execute(stmt)
        return [self._task_to_summary(task) for task in result.scalars().all()]

    async def create_task(self, session: AsyncSession, user_id: str, payload: TaskCreateRequest) -> TaskSummary:
        await self._ensure_researcher_access(session, user_id, payload.researcher_id)
        task = OrchestrationTask(
            id=f"t_{uuid4().hex[:10]}",
            owner_id=user_id,
            title=payload.title,
            researcher_id=payload.researcher_id,
            schedule_type=payload.schedule_type,
            schedule_config=payload.schedule_config,
            trade_day_only=payload.trade_day_only,
            force_output_document=payload.force_output_document,
            description=payload.description,
            prompt_template=payload.prompt_template,
            lifecycle_status="DRAFT",
        )
        session.add(task)
        await session.commit()
        await session.refresh(task)
        return self._task_to_summary(task)

    async def update_task(
        self,
        session: AsyncSession,
        user_id: str,
        task_id: str,
        payload: TaskUpdateRequest,
    ) -> TaskSummary:
        task = await self._get_task_or_404(session, task_id, user_id=user_id)
        if task.lifecycle_status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法更新")

        updates = payload.model_dump(exclude_unset=True)
        if "researcher_id" in updates:
            await self._ensure_researcher_access(session, user_id, updates["researcher_id"])
        for key, value in updates.items():
            setattr(task, key, value)
        if task.lifecycle_status == "ACTIVE":
            await self._sync_scheduler(task)
        await session.commit()
        await session.refresh(task)
        return self._task_to_summary(task)

    async def delete_task(self, session: AsyncSession, user_id: str, task_id: str) -> TaskSummary:
        task = await self._get_task_or_404(session, task_id, user_id=user_id)
        task.lifecycle_status = "DELETED"
        task.next_run_at = None
        await self._remove_scheduler(task.id)
        await session.commit()
        await session.refresh(task)
        return self._task_to_summary(task)

    async def activate_task(self, session: AsyncSession, user_id: str, task_id: str) -> TaskSummary:
        task = await self._get_task_or_404(session, task_id, user_id=user_id)
        if task.lifecycle_status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法启用")
        task.lifecycle_status = "ACTIVE"
        await self._sync_scheduler(task)
        await session.commit()
        await session.refresh(task)
        return self._task_to_summary(task)

    async def pause_task(self, session: AsyncSession, user_id: str, task_id: str) -> TaskSummary:
        task = await self._get_task_or_404(session, task_id, user_id=user_id)
        if task.lifecycle_status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法暂停")
        if task.lifecycle_status == "DRAFT":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="草稿任务无需暂停")
        task.lifecycle_status = "PAUSED"
        task.next_run_at = None
        await self._remove_scheduler(task.id)
        await session.commit()
        await session.refresh(task)
        return self._task_to_summary(task)

    async def run_task(self, session: AsyncSession, user_id: str, task_id: str) -> TaskRunRecord:
        task = await self._get_task_or_404(session, task_id, user_id=user_id)
        if task.lifecycle_status == "DELETED":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务已删除，无法执行")
        return await self.execute_task(session, task_id, trigger_source="manual")

    async def execute_task(self, session: AsyncSession, task_id: str, *, trigger_source: str) -> TaskRunRecord:
        task = await self._get_task_or_404(session, task_id)
        now = datetime.now(tz=UTC)
        run = OrchestrationTaskRun(
            id=f"tr_{uuid4().hex[:12]}",
            task_id=task.id,
            trigger_time=now,
            start_time=now,
            status="RUNNING",
            result_type="none",
            rendered_prompt="",
        )
        session.add(run)
        await self._add_log(session, run.id, "INFO", f"任务触发：{task.title}（{trigger_source}）", now)
        await session.flush()

        try:
            if task.trade_day_only and not await self._is_trade_day(now):
                await self._finish_run(session, task, run, "SKIPPED", "none", "非交易日，已跳过执行")
                await self._add_log(session, run.id, "WARNING", "非交易日限制生效，本次执行标记为 SKIPPED")
                await session.commit()
                return self._run_to_record(run)

            researcher = await session.get(Researcher, task.researcher_id)
            if not researcher:
                raise RuntimeError(f"研究员不存在：{task.researcher_id}")

            rendered_prompt = await self._render_prompt(task.prompt_template)
            run.rendered_prompt = rendered_prompt
            await self._add_log(session, run.id, "INFO", "动态变量渲染完成，开始调用 LLM")
            markdown = await self._generate_markdown(task, rendered_prompt)
            await self._add_log(session, run.id, "INFO", "LLM Markdown 生成完成")

            result_type = "message"
            document_id: str | None = None
            if task.force_output_document:
                document = Document(
                    id=f"d_{uuid4().hex[:12]}",
                    researcher_id=researcher.id,
                    author_id=task.owner_id,
                    title=task.title,
                    summary=task.description[:300],
                    content=markdown,
                    doc_type="report",
                )
                session.add(document)
                document_id = document.id
                result_type = "document"
                await self._add_log(session, run.id, "INFO", f"已写入文档：{document_id}")

            run.result_document_id = document_id
            await self._finish_run(session, task, run, "SUCCESS", result_type, None)
        except Exception as exc:
            message = str(exc) or exc.__class__.__name__
            await self._finish_run(session, task, run, "FAILED", "none", message)
            await self._add_log(session, run.id, "ERROR", f"执行失败：{message}")

        await session.commit()
        await session.refresh(run)
        return self._run_to_record(run)

    async def list_runs(
        self,
        session: AsyncSession,
        *,
        user_id: str,
        task_id: str | None = None,
    ) -> list[TaskRunRecord]:
        stmt = (
            select(OrchestrationTaskRun)
            .join(OrchestrationTask, OrchestrationTask.id == OrchestrationTaskRun.task_id)
            .where(OrchestrationTask.owner_id == user_id)
            .order_by(OrchestrationTaskRun.trigger_time.desc())
        )
        if task_id:
            stmt = stmt.where(OrchestrationTaskRun.task_id == task_id)
        result = await session.execute(stmt)
        return [self._run_to_record(run) for run in result.scalars().all()]

    async def list_task_runs(self, session: AsyncSession, user_id: str, task_id: str) -> list[TaskRunRecord]:
        await self._get_task_or_404(session, task_id, user_id=user_id)
        return await self.list_runs(session, user_id=user_id, task_id=task_id)

    async def list_run_logs(self, session: AsyncSession, user_id: str, run_id: str) -> list[TaskRunLog]:
        stmt = (
            select(OrchestrationTaskRun)
            .join(OrchestrationTask, OrchestrationTask.id == OrchestrationTaskRun.task_id)
            .where(OrchestrationTaskRun.id == run_id, OrchestrationTask.owner_id == user_id)
        )
        result = await session.execute(stmt)
        run = result.scalar_one_or_none()
        if run is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="执行记录不存在")
        stmt = (
            select(OrchestrationTaskRunLog)
            .where(OrchestrationTaskRunLog.run_id == run_id)
            .order_by(OrchestrationTaskRunLog.created_at.asc())
        )
        result = await session.execute(stmt)
        return [self._log_to_schema(log) for log in result.scalars().all()]

    async def _get_task_or_404(
        self,
        session: AsyncSession,
        task_id: str,
        *,
        user_id: str | None = None,
    ) -> OrchestrationTask:
        if user_id is None:
            task = await session.get(OrchestrationTask, task_id)
        else:
            stmt = select(OrchestrationTask).where(
                OrchestrationTask.id == task_id,
                OrchestrationTask.owner_id == user_id,
            )
            result = await session.execute(stmt)
            task = result.scalar_one_or_none()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        return task

    async def _ensure_researcher_access(self, session: AsyncSession, user_id: str, researcher_id: str) -> None:
        researcher = await session.get(Researcher, researcher_id)
        if researcher is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="研究员不存在")
        if researcher.owner_id == user_id or researcher.is_system or researcher.visibility == "public":
            return
        stmt = select(ResearcherHire.id).where(
            ResearcherHire.user_id == user_id,
            ResearcherHire.researcher_id == researcher_id,
            ResearcherHire.status == "hired",
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权使用该研究员创建任务")

    @staticmethod
    def _task_to_summary(task: OrchestrationTask) -> TaskSummary:
        return TaskSummary(
            task_id=task.id,
            title=task.title,
            researcher_id=task.researcher_id,
            schedule_type=task.schedule_type,
            schedule_config=task.schedule_config,
            trade_day_only=task.trade_day_only,
            force_output_document=task.force_output_document,
            description=task.description,
            prompt_template=task.prompt_template,
            status=task.lifecycle_status,
            lifecycle_status=task.lifecycle_status,
            created_at=task.created_at,
            updated_at=task.updated_at,
            last_run_at=task.last_run_at,
            last_run_status=task.last_run_status,
            next_run_at=task.next_run_at,
        )

    @staticmethod
    def _run_to_record(run: OrchestrationTaskRun) -> TaskRunRecord:
        return TaskRunRecord(
            run_id=run.id,
            task_id=run.task_id,
            trigger_time=run.trigger_time,
            start_time=run.start_time,
            end_time=run.end_time,
            status=run.status,
            result_type=run.result_type,
            result_document_id=run.result_document_id,
            error_message=run.error_message,
        )

    @staticmethod
    def _log_to_schema(log: OrchestrationTaskRunLog) -> TaskRunLog:
        return TaskRunLog(
            log_id=log.id,
            run_id=log.run_id,
            level=log.level,
            content=log.content,
            create_time=log.created_at,
        )

    async def _finish_run(
        self,
        session: AsyncSession,
        task: OrchestrationTask,
        run: OrchestrationTaskRun,
        run_status: TaskRunStatus,
        result_type: str,
        error_message: str | None,
    ) -> None:
        end_time = datetime.now(tz=UTC)
        run.status = run_status
        run.end_time = end_time
        run.result_type = result_type
        run.error_message = error_message
        task.last_run_at = end_time
        task.last_run_status = run_status
        if task.lifecycle_status == "ACTIVE":
            from app.engine.scheduler import get_orchestration_task_next_run_at

            task.next_run_at = get_orchestration_task_next_run_at(task.id)
        await session.flush()

    async def _add_log(
        self,
        session: AsyncSession,
        run_id: str,
        level: str,
        content: str,
        created_at: datetime | None = None,
    ) -> None:
        session.add(OrchestrationTaskRunLog(
            id=f"log_{uuid4().hex[:10]}",
            run_id=run_id,
            level=level,
            content=content,
            created_at=created_at or datetime.now(tz=UTC),
        ))
        await session.flush()

    async def _generate_markdown(self, task: OrchestrationTask, rendered_prompt: str) -> str:
        client = get_llm_client()
        return await client.chat(
            [
                LLMMessage(role="system", content="你是专业投研助手。请输出结构化 Markdown，不要返回 JSON。"),
                LLMMessage(role="user", content=rendered_prompt),
            ],
            temperature=0.4,
            max_tokens=3000,
        )

    async def _render_prompt(self, template: str) -> str:
        now = datetime.now(tz=ZoneInfo("Asia/Shanghai"))
        values = {
            "date": now.date().isoformat(),
            "lastDate": (now.date() - timedelta(days=1)).isoformat(),
            "nextDate": (now.date() + timedelta(days=1)).isoformat(),
            "lastTradeDate": (await self._shift_trade_day(now, -1)).isoformat(),
            "nextTradeDate": (await self._shift_trade_day(now, 1)).isoformat(),
        }
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", value)
        return rendered

    @staticmethod
    def _is_trade_date(value: datetime | date) -> bool:
        current = value.date() if isinstance(value, datetime) else value
        dates = list_recent_trade_dates(current, 1)
        return bool(dates and dates[-1] == current)

    async def _shift_trade_day(self, now: datetime, direction: int) -> date:
        current = now.date()
        while True:
            current += timedelta(days=direction)
            if await run_sync(self._is_trade_date, current):
                return current

    async def _is_trade_day(self, value: datetime) -> bool:
        local_date = value.astimezone(ZoneInfo("Asia/Shanghai")).date()
        return await run_sync(self._is_trade_date, local_date)

    @staticmethod
    def _coerce_lifecycle_status(status_value: TaskStatus) -> TaskLifecycleStatus | None:
        return status_value if status_value in {"DRAFT", "ACTIVE", "PAUSED", "DELETED"} else None

    async def _sync_scheduler(self, task: OrchestrationTask) -> None:
        from app.engine.scheduler import schedule_orchestration_task

        task.next_run_at = schedule_orchestration_task(task)

    async def _remove_scheduler(self, task_id: str) -> None:
        from app.engine.scheduler import unschedule_orchestration_task

        unschedule_orchestration_task(task_id)
