"""Workspace LAN subnet for self-serve onboarding (Phase 3.5).

Adds `workspaces.lan_subnet` so customers can declare which on-prem CIDR
their OLTs live on. The cloud hub uses this to add `wg0` allowed-ips and
a kernel route during the Connect Router wizard, removing the need for
manual `wg set` / `ip route add` after every signup.

Revision ID: 0007_workspace_lan_subnet
Revises: 0006_feedback
Create Date: 2026-04-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0007_workspace_lan_subnet"
down_revision = "0006_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column("lan_subnet", sa.String(43), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "lan_subnet")
