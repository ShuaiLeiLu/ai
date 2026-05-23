"""add pending_orders

Revision ID: d6e7f8a9b0c1
Revises: c5e6f7a8b9c0
Create Date: 2026-05-22 00:05:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d6e7f8a9b0c1"
down_revision = "c5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_orders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("account_id", sa.String(length=36), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("filled_trade_id", sa.String(length=36), nullable=True),
        sa.Column("filled_price", sa.Float(), nullable=True),
        sa.Column("filled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["trading_accounts.id"], ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_pending_orders_account_id",
        "pending_orders",
        ["account_id"],
    )
    op.create_index(
        "ix_pending_orders_account_status",
        "pending_orders",
        ["account_id", "status"],
    )
    op.create_index(
        "ix_pending_orders_symbol_status",
        "pending_orders",
        ["symbol", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_pending_orders_symbol_status", table_name="pending_orders")
    op.drop_index("ix_pending_orders_account_status", table_name="pending_orders")
    op.drop_index("ix_pending_orders_account_id", table_name="pending_orders")
    op.drop_table("pending_orders")
