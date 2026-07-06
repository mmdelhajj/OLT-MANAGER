"""Agent API keys table (local agent -> SaaS push auth).

The AgentKey ORM model shipped without an Alembic migration, so a fresh
Postgres/SaaS deploy had no agent_keys table and every /api/agent/* call failed
with UndefinedTable. This creates it to match models.py::AgentKey.

Revision ID: 0009_agent_keys
Revises: 0008_olt_snmp_community
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_agent_keys"
down_revision = "0008_olt_snmp_community"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.String(36), sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("name", sa.String(100), server_default="Default Agent"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_ip", sa.String(45), nullable=True),
        sa.Column("agent_version", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_agent_keys_tenant_id", "agent_keys", ["tenant_id"])
    op.create_index("ix_agent_keys_workspace_id", "agent_keys", ["workspace_id"])
    op.create_index("ix_agent_keys_key_hash", "agent_keys", ["key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_agent_keys_key_hash", table_name="agent_keys")
    op.drop_index("ix_agent_keys_workspace_id", table_name="agent_keys")
    op.drop_index("ix_agent_keys_tenant_id", table_name="agent_keys")
    op.drop_table("agent_keys")
