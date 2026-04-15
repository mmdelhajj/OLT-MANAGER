"""WireGuard subnet allocations table (Phase 3.2).

Revision ID: 0005_wireguard_subnets
Revises: 0004_rls
Create Date: 2026-04-11
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005_wireguard_subnets"
down_revision = "0004_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wireguard_subnets",
        sa.Column("cidr", sa.String(43), primary_key=True),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "allocated_at",
            sa.DateTime,
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_wireguard_subnets_workspace_id",
        "wireguard_subnets",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_wireguard_subnets_workspace_id", table_name="wireguard_subnets")
    op.drop_table("wireguard_subnets")
