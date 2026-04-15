"""Add Tenant + Workspace tables and the user_workspaces association.

This migration introduces multi-tenancy as new tables. It does NOT yet
touch the existing 19 single-tenant tables — that's migration 0003.

Revision ID: 0002_tenants_and_workspaces
Revises: 0001_baseline
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_tenants_and_workspaces"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(63), nullable=False, unique=True),
        sa.Column("stripe_customer_id", sa.String(64), nullable=True),
        sa.Column("plan", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("status", sa.String(20), nullable=False, server_default="trial"),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("dek_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)
    op.create_index("ix_tenants_stripe_customer_id", "tenants", ["stripe_customer_id"])

    op.create_table(
        "workspaces",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("wg_subnet", sa.String(43), nullable=True),
        sa.Column("wg_pubkey", sa.String(64), nullable=True),
        sa.Column("wg_privkey_enc", sa.Text(), nullable=True),
        sa.Column("wg_status", sa.String(20), server_default="pending"),
        sa.Column("last_handshake_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_workspaces_tenant_name"),
    )
    op.create_index("ix_workspaces_tenant_id", "workspaces", ["tenant_id"])

    op.create_table(
        "user_workspaces",
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column(
            "workspace_id",
            sa.String(36),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False, server_default="operator"),
        sa.PrimaryKeyConstraint("user_id", "workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("user_workspaces")
    op.drop_index("ix_workspaces_tenant_id", table_name="workspaces")
    op.drop_table("workspaces")
    op.drop_index("ix_tenants_stripe_customer_id", table_name="tenants")
    op.drop_index("ix_tenants_slug", table_name="tenants")
    op.drop_table("tenants")
