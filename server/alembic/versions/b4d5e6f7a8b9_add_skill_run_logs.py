"""add skill run logs

Revision ID: b4d5e6f7a8b9
Revises: a3c4d5e6f7a8
Create Date: 2026-05-22 00:03:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "b4d5e6f7a8b9"
down_revision = "a3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skill_run_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("skill_name", sa.Text(), nullable=False),
        sa.Column("chain_kind", sa.Text(), nullable=False, server_default=""),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("researcher_id", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("narrative_len", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_skill_run_logs_skill_name_created",
        "skill_run_logs",
        ["skill_name", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_skill_run_logs_skill_name_created", table_name="skill_run_logs")
    op.drop_table("skill_run_logs")
