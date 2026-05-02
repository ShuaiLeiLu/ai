"""add_trading_perf_indexes

Revision ID: 4b3d4e2a11a7
Revises: b5e3b7731a16
Create Date: 2026-04-22 23:35:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "4b3d4e2a11a7"
down_revision: Union[str, None] = "b5e3b7731a16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trading_accounts_user_researcher "
        "ON trading_accounts (user_id, researcher_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_positions_account_symbol "
        "ON positions (account_id, symbol)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_trade_records_account_created_at "
        "ON trade_records (account_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_trade_records_account_created_at")
    op.execute("DROP INDEX IF EXISTS ix_positions_account_symbol")
    op.execute("DROP INDEX IF EXISTS ix_trading_accounts_user_researcher")
