"""Indexes for hot poll-path lookups.

Every poll cycle filters onus/traffic_snapshots by olt_id (+ mac_address), and
does a per-ONU ONU.filter(olt_id, mac_address).first(). Postgres doesn't
auto-index FKs, so these were full scans that worsen as data grows. Add
composite indexes matching the query predicates.

Revision ID: 0011_poll_path_indexes
Revises: 0010_olt_mk_columns
Create Date: 2026-07-06
"""
from __future__ import annotations

from alembic import op


revision = "0011_poll_path_indexes"
down_revision = "0010_olt_mk_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_onus_olt_mac", "onus", ["olt_id", "mac_address"])
    op.create_index("ix_traffic_snapshots_olt_mac", "traffic_snapshots", ["olt_id", "mac_address"])
    op.create_index("ix_poll_logs_olt_id", "poll_logs", ["olt_id"])


def downgrade() -> None:
    op.drop_index("ix_poll_logs_olt_id", table_name="poll_logs")
    op.drop_index("ix_traffic_snapshots_olt_mac", table_name="traffic_snapshots")
    op.drop_index("ix_onus_olt_mac", table_name="onus")
