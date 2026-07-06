"""OLT Mikrotik integration columns.

OLT.mk_ip/mk_username/mk_password/mk_port/mk_enabled shipped on the model but
were never added by Alembic (or run_migrations), so any DB not built by
create_all() throws OperationalError: no such column: olts.mk_ip on every OLT
query. Add them to match models.py::OLT.

Revision ID: 0010_olt_mk_columns
Revises: 0009_agent_keys
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0010_olt_mk_columns"
down_revision = "0009_agent_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("olts", sa.Column("mk_ip", sa.String(45), nullable=True))
    op.add_column("olts", sa.Column("mk_username", sa.String(100), nullable=True))
    op.add_column("olts", sa.Column("mk_password", sa.String(255), nullable=True))
    op.add_column("olts", sa.Column("mk_port", sa.Integer(), server_default="8728"))
    op.add_column("olts", sa.Column("mk_enabled", sa.Boolean(), server_default=sa.false()))


def downgrade() -> None:
    for col in ("mk_enabled", "mk_port", "mk_password", "mk_username", "mk_ip"):
        op.drop_column("olts", col)
