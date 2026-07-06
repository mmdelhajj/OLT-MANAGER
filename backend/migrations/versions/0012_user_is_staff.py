"""users.is_staff flag (internal cross-tenant support access).

The /admin/feedback endpoint gates on user.is_staff, but the column was never
created, so the check was always False (endpoint permanently dead). Add it.

Revision ID: 0012_user_is_staff
Revises: 0011_poll_path_indexes
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0012_user_is_staff"
down_revision = "0011_poll_path_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_staff", sa.Boolean(), server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_staff")
