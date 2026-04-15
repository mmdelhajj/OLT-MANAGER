"""In-app feedback table (Phase 6).

Revision ID: 0006_feedback
Revises: 0005_wireguard_subnets
Create Date: 2026-04-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0006_feedback"
down_revision = "0005_wireguard_subnets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("page_url", sa.String(500), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_feedback_tenant_id", "feedback", ["tenant_id"])
    op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
    op.create_index("ix_feedback_created_at", "feedback", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_feedback_created_at", table_name="feedback")
    op.drop_index("ix_feedback_user_id", table_name="feedback")
    op.drop_index("ix_feedback_tenant_id", table_name="feedback")
    op.drop_table("feedback")
