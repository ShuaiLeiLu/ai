from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class OrchestrationTask(Base, TimestampMixin):
    __tablename__ = "orchestration_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    researcher_id: Mapped[str] = mapped_column(String(36), ForeignKey("researchers.id"), nullable=False, index=True)
    schedule_type: Mapped[str] = mapped_column(String(20), nullable=False)
    schedule_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    trade_day_only: Mapped[bool] = mapped_column(nullable=False, default=False)
    force_output_document: Mapped[bool] = mapped_column(nullable=False, default=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Lifecycle status: DRAFT / ACTIVE / PAUSED / DELETED.
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default="DRAFT", index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    runs = relationship("OrchestrationTaskRun", back_populates="task", lazy="selectin")


class OrchestrationTaskRun(Base, TimestampMixin):
    __tablename__ = "orchestration_task_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(36), ForeignKey("orchestration_tasks.id"), nullable=False, index=True)
    trigger_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    result_type: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    result_document_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("documents.id"), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    rendered_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")

    task = relationship("OrchestrationTask", back_populates="runs")
    logs = relationship("OrchestrationTaskRunLog", back_populates="run", lazy="selectin")


class OrchestrationTaskRunLog(Base):
    __tablename__ = "orchestration_task_run_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("orchestration_task_runs.id"), nullable=False, index=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False, default="INFO")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    run = relationship("OrchestrationTaskRun", back_populates="logs")
