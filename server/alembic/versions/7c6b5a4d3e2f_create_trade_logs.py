"""create_trade_logs

Revision ID: 7c6b5a4d3e2f
Revises: c1a2b3d4e5f6
Create Date: 2026-05-02 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "7c6b5a4d3e2f"
down_revision: Union[str, None] = "c1a2b3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS trade_logs (
            id VARCHAR(36) NOT NULL,
            account_id VARCHAR(36) NOT NULL,
            log_type VARCHAR(20) NOT NULL,
            trade_record_ids TEXT NOT NULL,
            content TEXT NOT NULL,
            title VARCHAR(200) NOT NULL,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            FOREIGN KEY(account_id) REFERENCES trading_accounts (id),
            PRIMARY KEY (id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trade_logs_account_id "
        "ON trade_logs (account_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trade_logs_account_created_at "
        "ON trade_logs (account_id, created_at)"
    )


def downgrade() -> None:
    op.drop_index("ix_trade_logs_account_created_at", table_name="trade_logs")
    op.drop_index(op.f("ix_trade_logs_account_id"), table_name="trade_logs")
    op.drop_table("trade_logs")
