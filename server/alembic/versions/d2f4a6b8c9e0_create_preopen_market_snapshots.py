"""create preopen market snapshots

Revision ID: d2f4a6b8c9e0
Revises: 7c6b5a4d3e2f
Create Date: 2026-05-17 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "d2f4a6b8c9e0"
down_revision = "7c6b5a4d3e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preopen_market_snapshots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("limit_up_count", sa.Integer(), nullable=False),
        sa.Column("limit_down_count", sa.Integer(), nullable=False),
        sa.Column("consecutive_limit_up_count", sa.Integer(), nullable=False),
        sa.Column("highest_consecutive", sa.Integer(), nullable=False),
        sa.Column("strong_count", sa.Integer(), nullable=False),
        sa.Column("break_count", sa.Integer(), nullable=False),
        sa.Column("seal_ratio", sa.Float(), nullable=False),
        sa.Column("top_industries", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_preopen_market_snapshots_trade_date",
        "preopen_market_snapshots",
        ["trade_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_preopen_market_snapshots_trade_date", table_name="preopen_market_snapshots")
    op.drop_table("preopen_market_snapshots")
