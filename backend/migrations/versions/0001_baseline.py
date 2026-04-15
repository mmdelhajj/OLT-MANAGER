"""Baseline schema (pre-Phase-1, single tenant).

Recreates the 19-table schema as it existed in the SQLite single-tenant
binary, so a fresh Postgres database can `alembic upgrade 0001` and end up
in exactly the same state the single-tenant production binary boots into.

The Phase 1 changes (tenant_id, workspaces, RLS) are applied by 0002, 0003
and 0004 on top of this baseline.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="operator"),
        sa.Column("full_name", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "olts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password", sa.String(255), nullable=False),
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("pon_ports", sa.Integer(), server_default="8"),
        sa.Column("is_online", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("last_poll", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("web_username", sa.String(100), nullable=True),
        sa.Column("web_password", sa.String(255), nullable=True),
        sa.Column("cpu_usage", sa.Integer(), nullable=True),
        sa.Column("memory_usage", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Integer(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "regions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("color", sa.String(7), server_default="#3B82F6"),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "onus",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=False),
        sa.Column("region_id", sa.Integer(), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("pon_port", sa.Integer(), nullable=False),
        sa.Column("onu_id", sa.Integer(), nullable=False),
        sa.Column("mac_address", sa.String(17), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("is_online", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("model", sa.String(50), nullable=True),
        sa.Column("distance", sa.Integer(), nullable=True),
        sa.Column("rx_power", sa.Float(), nullable=True),
        sa.Column("onu_rx_power", sa.Float(), nullable=True),
        sa.Column("onu_tx_power", sa.Float(), nullable=True),
        sa.Column("onu_temperature", sa.Float(), nullable=True),
        sa.Column("onu_voltage", sa.Float(), nullable=True),
        sa.Column("onu_tx_bias", sa.Float(), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("image_urls", sa.Text(), nullable=True),
        sa.Column("missing_polls", sa.Integer(), server_default="0"),
        sa.Column("online_since", sa.DateTime(), nullable=True),
        sa.Column("olt_alive_time", sa.Integer(), nullable=True),
        sa.Column("offline_reason", sa.String(50), nullable=True),
        sa.Column("last_seen", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "user_olts",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), primary_key=True),
    )

    op.create_table(
        "poll_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("onus_found", sa.Integer(), server_default="0"),
        sa.Column("polled_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "traffic_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=False),
        sa.Column("mac_address", sa.String(17), nullable=False),
        sa.Column("rx_bytes", sa.BigInteger(), server_default="0"),
        sa.Column("tx_bytes", sa.BigInteger(), server_default="0"),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("last_rx_kbps", sa.Float(), server_default="0"),
        sa.Column("last_tx_kbps", sa.Float(), server_default="0"),
    )

    op.create_table(
        "traffic_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("entity_type", sa.String(10), nullable=False, index=True),
        sa.Column("entity_id", sa.String(50), nullable=False, index=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=False, index=True),
        sa.Column("pon_port", sa.Integer(), nullable=True),
        sa.Column("onu_db_id", sa.Integer(), sa.ForeignKey("onus.id"), nullable=True),
        sa.Column("rx_kbps", sa.Float(), server_default="0"),
        sa.Column("tx_kbps", sa.Float(), server_default="0"),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "olt_ports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=False, index=True),
        sa.Column("port_type", sa.String(10), nullable=False),
        sa.Column("port_number", sa.Integer(), nullable=False),
        sa.Column("if_index", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(10), server_default="unknown"),
        sa.Column("onu_count", sa.Integer(), server_default="0"),
        sa.Column("tx_power", sa.Float(), nullable=True),
        sa.Column("rx_power", sa.Float(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("speed", sa.String(20), nullable=True),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "port_traffic",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=False, index=True),
        sa.Column("port_type", sa.String(10), nullable=False),
        sa.Column("port_number", sa.Integer(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column("rx_kbps", sa.Float(), server_default="0"),
        sa.Column("tx_kbps", sa.Float(), server_default="0"),
    )

    op.create_table(
        "settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(50), nullable=False, unique=True),
        sa.Column("value", sa.String(500), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "diagrams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("nodes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("connections", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("settings", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("is_shared", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "event_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False, index=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=True),
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("schedule_type", sa.String(20), nullable=False),
        sa.Column("schedule_time", sa.String(10), nullable=False),
        sa.Column("schedule_day", sa.Integer(), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("next_run", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "config_backups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("olt_id", sa.Integer(), sa.ForeignKey("olts.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("backup_type", sa.String(20), server_default="manual"),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "alert_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("rule_type", sa.String(50), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("comparison", sa.String(10), nullable=True),
        sa.Column("notify_email", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("notify_sms", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("notify_whatsapp", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("is_enabled", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("cooldown_minutes", sa.Integer(), server_default="60"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "sent_alerts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alert_rule_id", sa.Integer(), sa.ForeignKey("alert_rules.id"), nullable=False),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("sent_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "system_backups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("backup_type", sa.String(20), server_default="manual"),
        sa.Column("storage_type", sa.String(20), server_default="local"),
        sa.Column("storage_path", sa.String(500), nullable=True),
        sa.Column("includes_db", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("includes_config", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("includes_uploads", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("status", sa.String(20), server_default="completed"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        "backup_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("auto_backup_enabled", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("backup_frequency", sa.String(20), server_default="daily"),
        sa.Column("backup_time", sa.String(10), server_default="02:00"),
        sa.Column("backup_day", sa.Integer(), nullable=True),
        sa.Column("retention_days", sa.Integer(), server_default="30"),
        sa.Column("backup_database", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("backup_config", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("backup_uploads", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("storage_type", sa.String(20), server_default="local"),
        sa.Column("local_path", sa.String(500), server_default="/opt/olt-manager/backups"),
        sa.Column("ftp_host", sa.String(255), nullable=True),
        sa.Column("ftp_port", sa.Integer(), server_default="21"),
        sa.Column("ftp_username", sa.String(100), nullable=True),
        sa.Column("ftp_password", sa.String(255), nullable=True),
        sa.Column("ftp_path", sa.String(255), server_default="/backups"),
        sa.Column("ftp_use_sftp", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("s3_bucket", sa.String(255), nullable=True),
        sa.Column("s3_region", sa.String(50), nullable=True),
        sa.Column("s3_access_key", sa.String(255), nullable=True),
        sa.Column("s3_secret_key", sa.String(255), nullable=True),
        sa.Column("s3_path", sa.String(255), server_default="/olt-manager-backups"),
        sa.Column("last_backup_at", sa.DateTime(), nullable=True),
        sa.Column("last_backup_status", sa.String(20), nullable=True),
        sa.Column("next_backup_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    for tbl in [
        "backup_settings",
        "system_backups",
        "sent_alerts",
        "alert_rules",
        "config_backups",
        "scheduled_tasks",
        "event_logs",
        "diagrams",
        "settings",
        "port_traffic",
        "olt_ports",
        "traffic_history",
        "traffic_snapshots",
        "poll_logs",
        "user_olts",
        "onus",
        "regions",
        "olts",
        "users",
    ]:
        op.drop_table(tbl)
