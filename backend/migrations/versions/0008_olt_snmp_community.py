"""Per-OLT SNMP community.

Adds `olts.snmp_community` so each OLT can use a non-default SNMP read
community instead of the previously hardcoded "public". The driver/poll layer
already reads `olt.snmp_community` (falling back to "public"); this migration
adds the backing column on Postgres (SQLite installs get it via the in-process
run_migrations() helper).

Revision ID: 0008_olt_snmp_community
Revises: 0007_workspace_lan_subnet
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0008_olt_snmp_community"
down_revision = "0007_workspace_lan_subnet"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "olts",
        sa.Column("snmp_community", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("olts", "snmp_community")
