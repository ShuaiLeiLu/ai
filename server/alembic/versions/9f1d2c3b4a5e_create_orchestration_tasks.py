"""create_orchestration_tasks

Revision ID: 9f1d2c3b4a5e
Revises: 4b3d4e2a11a7
Create Date: 2026-05-02 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9f1d2c3b4a5e"
down_revision: Union[str, None] = "4b3d4e2a11a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "orchestration_tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("researcher_id", sa.String(length=36), nullable=False),
        sa.Column("schedule_type", sa.String(length=20), nullable=False),
        sa.Column("schedule_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trade_day_only", sa.Boolean(), nullable=False),
        sa.Column("force_output_document", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("lifecycle_status", sa.String(length=20), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(length=20), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["researcher_id"], ["researchers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orchestration_tasks_owner_id", "orchestration_tasks", ["owner_id"])
    op.create_index("ix_orchestration_tasks_researcher_id", "orchestration_tasks", ["researcher_id"])
    op.create_index("ix_orchestration_tasks_lifecycle_status", "orchestration_tasks", ["lifecycle_status"])

    op.create_table(
        "orchestration_task_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("trigger_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("result_type", sa.String(length=20), nullable=False),
        sa.Column("result_document_id", sa.String(length=36), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("rendered_prompt", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["result_document_id"], ["documents.id"]),
        sa.ForeignKeyConstraint(["task_id"], ["orchestration_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orchestration_task_runs_task_id", "orchestration_task_runs", ["task_id"])
    op.create_index("ix_orchestration_task_runs_status", "orchestration_task_runs", ["status"])

    op.create_table(
        "orchestration_task_run_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("level", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["orchestration_task_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orchestration_task_run_logs_run_id", "orchestration_task_run_logs", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_orchestration_task_run_logs_run_id", table_name="orchestration_task_run_logs")
    op.drop_table("orchestration_task_run_logs")
    op.drop_index("ix_orchestration_task_runs_status", table_name="orchestration_task_runs")
    op.drop_index("ix_orchestration_task_runs_task_id", table_name="orchestration_task_runs")
    op.drop_table("orchestration_task_runs")
    op.drop_index("ix_orchestration_tasks_lifecycle_status", table_name="orchestration_tasks")
    op.drop_index("ix_orchestration_tasks_researcher_id", table_name="orchestration_tasks")
    op.drop_index("ix_orchestration_tasks_owner_id", table_name="orchestration_tasks")
    op.drop_table("orchestration_tasks")
