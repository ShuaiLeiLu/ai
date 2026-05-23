"""add trading account minute snapshots

Revision ID: c5e6f7a8b9c0
Revises: b4d5e6f7a8b9
Create Date: 2026-05-22 00:04:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c5e6f7a8b9c0"
down_revision = "b4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trading_account_minute_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("total_asset", sa.Float(), nullable=False),
        sa.Column("available_cash", sa.Float(), nullable=False),
        sa.Column("holding_value", sa.Float(), nullable=False),
        sa.Column("daily_pnl", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["trading_accounts.id"], ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_trading_account_minute_snapshots_account_id",
        "trading_account_minute_snapshots",
        ["account_id"],
    )
    op.create_index(
        "ix_trading_account_minute_snapshots_account_time",
        "trading_account_minute_snapshots",
        ["account_id", "snapshot_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_trading_account_minute_snapshots_account_time",
        table_name="trading_account_minute_snapshots",
    )
    op.drop_index(
        "ix_trading_account_minute_snapshots_account_id",
        table_name="trading_account_minute_snapshots",
    )
    op.drop_table("trading_account_minute_snapshots")
