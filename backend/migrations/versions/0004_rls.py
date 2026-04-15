"""Enable PostgreSQL Row-Level Security on every tenant-scoped table.

The application sets `app.current_tenant_id` via SET LOCAL at the start of
every transaction (see backend/models.py and backend/tenancy.py). RLS
policies installed here filter every SELECT/UPDATE/DELETE down to that
tenant_id, so individual queries can be written tenant-blind.

The OLT Manager database role must be a non-superuser for RLS to take
effect — superusers and table owners bypass policies by default. The
canonical setup creates a dedicated role::

    CREATE ROLE oltmanager_app LOGIN PASSWORD '...' NOSUPERUSER;
    GRANT USAGE ON SCHEMA public TO oltmanager_app;
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO oltmanager_app;

`alembic upgrade head` should be run as the migration role, but the running
FastAPI app should connect as `oltmanager_app`.

Revision ID: 0004_rls
Revises: 0003_add_tenant_id
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_rls"
down_revision: Union[str, None] = "0003_add_tenant_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every table that has a `tenant_id` column. Order doesn't matter for RLS.
RLS_TABLES = [
    "regions",
    "olts",
    "onus",
    "poll_logs",
    "traffic_snapshots",
    "traffic_history",
    "olt_ports",
    "port_traffic",
    "settings",
    "diagrams",
    "event_logs",
    "scheduled_tasks",
    "config_backups",
    "alert_rules",
    "sent_alerts",
    "system_backups",
    "backup_settings",
    "users",
    "workspaces",
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        # SQLite has no RLS; nothing to do.
        return

    for tbl in RLS_TABLES:
        # Enable RLS and force it (so even table owners obey it). FORCE
        # makes the policies apply to the connecting role unconditionally —
        # critical for catching superuser footguns in dev.
        bind.execute(sa.text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
        bind.execute(sa.text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))

        # Single policy that filters on the GUC. If the GUC is unset
        # (current_setting returns NULL), the policy denies all rows — this
        # is exactly the "fail closed" behavior we want for unscoped
        # connections.
        bind.execute(
            sa.text(
                f"""
                CREATE POLICY tenant_isolation ON {tbl}
                  USING (tenant_id::text = current_setting('app.current_tenant_id', true))
                  WITH CHECK (tenant_id::text = current_setting('app.current_tenant_id', true))
                """
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for tbl in RLS_TABLES:
        bind.execute(sa.text(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl}"))
        bind.execute(sa.text(f"ALTER TABLE {tbl} NO FORCE ROW LEVEL SECURITY"))
        bind.execute(sa.text(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY"))
