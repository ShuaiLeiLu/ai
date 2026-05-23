"""add preopen ai digests

Revision ID: e1a2b3c4d5f6
Revises: d2f4a6b8c9e0
Create Date: 2026-05-22 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "e1a2b3c4d5f6"
down_revision = "d2f4a6b8c9e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preopen_ai_digests",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("main_thesis_md", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "skill_outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "falsification_signals",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("bias", sa.Text(), nullable=False, server_default=""),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_preopen_ai_digests_trade_date",
        "preopen_ai_digests",
        ["trade_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_preopen_ai_digests_trade_date", table_name="preopen_ai_digests")
    op.drop_table("preopen_ai_digests")
