"""add trading account snapshots

Revision ID: c1a2b3d4e5f6
Revises: 9f1d2c3b4a5e
Create Date: 2026-05-02 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c1a2b3d4e5f6"
down_revision = "9f1d2c3b4a5e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trading_account_snapshots",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("total_asset", sa.Float(), nullable=False),
        sa.Column("available_cash", sa.Float(), nullable=False),
        sa.Column("holding_value", sa.Float(), nullable=False),
        sa.Column("daily_pnl", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["trading_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_trading_account_snapshots_account_date",
        "trading_account_snapshots",
        ["account_id", "trade_date"],
        unique=True,
    )
    op.create_index(
        op.f("ix_trading_account_snapshots_account_id"),
        "trading_account_snapshots",
        ["account_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_trading_account_snapshots_account_id"), table_name="trading_account_snapshots")
    op.drop_index("ix_trading_account_snapshots_account_date", table_name="trading_account_snapshots")
    op.drop_table("trading_account_snapshots")
