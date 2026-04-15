"""Backfill tenant_id (and workspace_id) onto every existing table.

Strategy:
    1. Create one bootstrap Tenant + one bootstrap Workspace.
    2. For each existing data table:
        a. ADD COLUMN tenant_id (nullable)
        b. UPDATE every row to point at the bootstrap tenant
        c. ALTER COLUMN tenant_id SET NOT NULL
    3. Where applicable (OLT, ONU, Region, Diagram), also add workspace_id.
    4. Reshuffle unique constraints:
        - olts.ip_address  -> (tenant_id, ip_address)
        - users.username   -> rename to email, unique on (tenant_id, email)
        - settings.key     -> (tenant_id, key)
    5. Migrate users.id from Integer to String(36) (UUID) and update FKs.
       NOTE: This is the trickiest part of Phase 1 — see the inline notes.

This migration is destructive in the sense that it changes user IDs from
integer auto-increments to UUID strings. The bootstrap tenant takes
ownership of every existing row, so no user data is lost.

Revision ID: 0003_add_tenant_id
Revises: 0002_tenants_and_workspaces
Create Date: 2026-04-11
"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_tenant_id"
down_revision: Union[str, None] = "0002_tenants_and_workspaces"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables that need tenant_id (every domain table).
# Some also need workspace_id (only those that represent regional resources).
TENANT_TABLES = [
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
]

WORKSPACE_TABLES = ["regions", "olts", "onus", "diagrams"]


def upgrade() -> None:
    bind = op.get_bind()

    # ------------------------------------------------------------------
    # 1. Bootstrap tenant + workspace
    # ------------------------------------------------------------------
    bootstrap_tenant_id = str(uuid.uuid4())
    bootstrap_workspace_id = str(uuid.uuid4())

    bind.execute(
        sa.text(
            "INSERT INTO tenants (id, name, slug, plan, status, created_at) "
            "VALUES (:id, :name, :slug, 'active', 'active', NOW())"
        ),
        {"id": bootstrap_tenant_id, "name": "Default", "slug": "default"},
    )
    bind.execute(
        sa.text(
            "INSERT INTO workspaces (id, tenant_id, name, wg_status, created_at) "
            "VALUES (:id, :tid, 'Default', 'pending', NOW())"
        ),
        {"id": bootstrap_workspace_id, "tid": bootstrap_tenant_id},
    )

    # ------------------------------------------------------------------
    # 2. Add tenant_id to every domain table, backfill, then NOT NULL
    # ------------------------------------------------------------------
    for tbl in TENANT_TABLES:
        op.add_column(tbl, sa.Column("tenant_id", sa.String(36), nullable=True))
        bind.execute(
            sa.text(f"UPDATE {tbl} SET tenant_id = :tid"),
            {"tid": bootstrap_tenant_id},
        )
        op.alter_column(tbl, "tenant_id", nullable=False)
        op.create_foreign_key(
            f"fk_{tbl}_tenant_id",
            tbl,
            "tenants",
            ["tenant_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{tbl}_tenant_id", tbl, ["tenant_id"])

    # ------------------------------------------------------------------
    # 3. Add workspace_id to regional tables, backfill, then NOT NULL
    # ------------------------------------------------------------------
    for tbl in WORKSPACE_TABLES:
        op.add_column(tbl, sa.Column("workspace_id", sa.String(36), nullable=True))
        bind.execute(
            sa.text(f"UPDATE {tbl} SET workspace_id = :wid"),
            {"wid": bootstrap_workspace_id},
        )
        op.alter_column(tbl, "workspace_id", nullable=False)
        op.create_foreign_key(
            f"fk_{tbl}_workspace_id",
            tbl,
            "workspaces",
            ["workspace_id"],
            ["id"],
            ondelete="CASCADE",
        )
        op.create_index(f"ix_{tbl}_workspace_id", tbl, ["workspace_id"])

    # ------------------------------------------------------------------
    # 4. Reshuffle unique constraints
    # ------------------------------------------------------------------
    op.drop_constraint("olts_ip_address_key", "olts", type_="unique")
    op.create_unique_constraint(
        "uq_olts_tenant_ip", "olts", ["tenant_id", "ip_address"]
    )

    op.drop_constraint("settings_key_key", "settings", type_="unique")
    op.create_unique_constraint(
        "uq_settings_tenant_key", "settings", ["tenant_id", "key"]
    )

    # ------------------------------------------------------------------
    # 5. Migrate users.id Integer -> String(36) (UUID), rename username -> email
    # ------------------------------------------------------------------
    # Postgres-specific approach: add new column, populate, swap, drop old.
    op.add_column("users", sa.Column("new_id", sa.String(36), nullable=True))
    op.add_column("users", sa.Column("email", sa.String(254), nullable=True))
    op.add_column("users", sa.Column("tenant_id", sa.String(36), nullable=True))
    op.add_column("users", sa.Column("email_verified_at", sa.DateTime(), nullable=True))

    rows = bind.execute(sa.text("SELECT id, username FROM users")).fetchall()
    id_map = {}  # old int id -> new uuid
    for row in rows:
        new_uuid = str(uuid.uuid4())
        id_map[row[0]] = new_uuid
        bind.execute(
            sa.text(
                "UPDATE users SET new_id = :nid, email = :em, tenant_id = :tid "
                "WHERE id = :oid"
            ),
            {
                "nid": new_uuid,
                "em": row[1],
                "tid": bootstrap_tenant_id,
                "oid": row[0],
            },
        )

    # Update foreign keys in dependent tables. They reference users.id as
    # Integer today; we need to convert them to String(36) referencing the
    # new UUIDs. Tables: regions.owner_id, diagrams.owner_id,
    # scheduled_tasks.created_by, config_backups.created_by,
    # system_backups.created_by, user_olts.user_id.
    fk_tables = [
        ("regions", "owner_id"),
        ("diagrams", "owner_id"),
        ("scheduled_tasks", "created_by"),
        ("config_backups", "created_by"),
        ("system_backups", "created_by"),
        ("user_olts", "user_id"),
    ]
    for tbl, col in fk_tables:
        op.add_column(tbl, sa.Column(f"new_{col}", sa.String(36), nullable=True))
        for old_id, new_uuid in id_map.items():
            bind.execute(
                sa.text(f"UPDATE {tbl} SET new_{col} = :nu WHERE {col} = :oi"),
                {"nu": new_uuid, "oi": old_id},
            )

    # Drop old FK columns and rename the new ones into place.
    # We do this *after* backfilling so foreign-key constraints stay valid.
    for tbl, col in fk_tables:
        # Look up the actual fk constraint name (Postgres auto-generates).
        bind.execute(
            sa.text(
                f"ALTER TABLE {tbl} DROP CONSTRAINT IF EXISTS {tbl}_{col}_fkey"
            )
        )
        op.drop_column(tbl, col)
        op.alter_column(tbl, f"new_{col}", new_column_name=col)

    # Drop the old users.id PK and swap in new_id.
    op.drop_constraint("users_pkey", "users", type_="primary")
    op.drop_constraint("users_username_key", "users", type_="unique")
    op.drop_column("users", "id")
    op.drop_column("users", "username")
    op.alter_column("users", "new_id", new_column_name="id", nullable=False)
    op.alter_column("users", "email", nullable=False)
    op.alter_column("users", "tenant_id", nullable=False)
    op.create_primary_key("users_pkey", "users", ["id"])
    op.create_unique_constraint(
        "uq_users_tenant_email", "users", ["tenant_id", "email"]
    )
    op.create_foreign_key(
        "fk_users_tenant_id",
        "users",
        "tenants",
        ["tenant_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Recreate FKs from dependent tables now that users.id is String(36).
    for tbl, col in fk_tables:
        op.create_foreign_key(
            f"fk_{tbl}_{col}_users",
            tbl,
            "users",
            [col],
            ["id"],
            ondelete="SET NULL" if col != "user_id" else "CASCADE",
        )


def downgrade() -> None:
    # Phase 1 is a one-way door. Rolling 0003 back is documented in the runbook
    # (`docs/runbooks/rollback-phase1.md` once Phase 5 lands) but is not
    # automated here, because going from per-tenant rows back to a single
    # global namespace would either drop data or pick a winner arbitrarily.
    raise NotImplementedError(
        "0003 is not auto-reversible. See docs/runbooks/rollback-phase1.md"
    )
