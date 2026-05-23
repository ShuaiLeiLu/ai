"""add daily review reports (embedding stored as JSONB)

Revision ID: a3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-05-22 00:02:00.000000

注:原本设计用 pgvector,但服务器未编译该扩展,改用 JSONB 落地 embedding,
RAG 余弦相似度由 Python 端计算。数据量大后可单独迁回 pgvector。
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a3c4d5e6f7a8"
down_revision = "f2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_review_reports",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("researcher_id", sa.String(length=36), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coach_report_md", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "skill_outputs",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("alpha_vs_index", sa.Float(), nullable=False, server_default="0"),
        sa.Column("alpha_vs_sector", sa.Float(), nullable=False, server_default="0"),
        sa.Column("win_rate", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_pnl", sa.Float(), nullable=False, server_default="0"),
        # embedding 数组(1536 维)以 JSONB 存,Python 端做余弦相似度
        sa.Column(
            "embedding",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["researcher_id"], ["researchers.id"], ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_daily_review_reports_researcher_id",
        "daily_review_reports",
        ["researcher_id"],
    )
    op.create_index(
        "ix_daily_review_reports_researcher_date",
        "daily_review_reports",
        ["researcher_id", "trade_date"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_daily_review_reports_researcher_date",
        table_name="daily_review_reports",
    )
    op.drop_index(
        "ix_daily_review_reports_researcher_id",
        table_name="daily_review_reports",
    )
    op.drop_table("daily_review_reports")
