"""add researcher thesis logs

Revision ID: f2b3c4d5e6f7
Revises: e1a2b3c4d5f6
Create Date: 2026-05-22 00:01:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "f2b3c4d5e6f7"
down_revision = "e1a2b3c4d5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "researcher_thesis_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("researcher_id", sa.String(length=36), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("direction_call", sa.String(length=32), nullable=False, server_default=""),
        sa.Column(
            "key_drivers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "falsification_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "actual_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "correctness",
            sa.String(length=20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["researcher_id"], ["researchers.id"], ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_researcher_thesis_logs_researcher_id",
        "researcher_thesis_logs",
        ["researcher_id"],
    )
    op.create_index(
        "ix_researcher_thesis_logs_researcher_date",
        "researcher_thesis_logs",
        ["researcher_id", "trade_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_researcher_thesis_logs_researcher_date",
        table_name="researcher_thesis_logs",
    )
    op.drop_index(
        "ix_researcher_thesis_logs_researcher_id",
        table_name="researcher_thesis_logs",
    )
    op.drop_table("researcher_thesis_logs")
