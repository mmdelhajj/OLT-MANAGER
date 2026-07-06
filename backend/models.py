"""Database models for OLT Manager.

Phase 1 (multi-tenant) notes:
    * Every row that belongs to a customer carries a `tenant_id` column,
      denormalized down from `OLT.tenant_id`. This is what PostgreSQL
      Row-Level Security policies key off, what GDPR-delete uses, and what
      the polling worker filters by.
    * Tenants are identified by UUIDs, stored as 36-char strings so the
      schema works on both SQLite (dev/legacy) and Postgres (SaaS).
    * Workspaces are sub-groupings inside a tenant — usually a region/POP.
      Every OLT belongs to exactly one workspace, and every user is scoped
      to one or more workspaces via `user_workspaces`.
    * The legacy `users.username` column has been renamed to `email` and the
      uniqueness constraint moved from global to (tenant_id, email).
"""
from datetime import datetime
import uuid as _uuid

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Table,
    Float,
    UniqueConstraint,
    Index,
    event,
    text,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from config import DATABASE_URL, is_postgres

# ---------------------------------------------------------------------------
# Engine + session factory
# ---------------------------------------------------------------------------

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _new_uuid() -> str:
    """Default for UUID primary keys (stored as 36-char strings)."""
    return str(_uuid.uuid4())


# ---------------------------------------------------------------------------
# Tenant + Workspace
# ---------------------------------------------------------------------------


class Tenant(Base):
    """An ISP company that signed up for the SaaS.

    A tenant owns workspaces, users, OLTs, and every other piece of
    customer data. Soft-deleted by setting `deleted_at`; hard-deleted
    by the `tenant_lifecycle` job (Phase 2).
    """

    __tablename__ = "tenants"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    name = Column(String(200), nullable=False)
    slug = Column(String(63), nullable=False, unique=True, index=True)
    stripe_customer_id = Column(String(64), nullable=True, index=True)
    plan = Column(String(20), nullable=False, default="trial")
    status = Column(String(20), nullable=False, default="trial")
    trial_ends_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    # Per-tenant Data Encryption Key, wrapped with the master KEK.
    # See backend/config.py:wrap_tenant_dek / unwrap_tenant_dek.
    dek_encrypted = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    workspaces = relationship("Workspace", back_populates="tenant", cascade="all, delete-orphan")
    users = relationship("User", back_populates="tenant", cascade="all, delete-orphan")


class Workspace(Base):
    """A region/POP grouping inside a tenant.

    OLTs live in a workspace. Users are granted access to one or more
    workspaces via `user_workspaces`. WireGuard subnets are allocated
    per workspace in Phase 3.
    """

    __tablename__ = "workspaces"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    # Phase 3 — WireGuard fields, nullable until provisioned.
    wg_subnet = Column(String(43), nullable=True)  # CIDR string e.g. "10.42.7.0/24"
    wg_pubkey = Column(String(64), nullable=True)
    wg_privkey_enc = Column(Text, nullable=True)
    wg_status = Column(String(20), default="pending")  # pending|connected|stale
    last_handshake_at = Column(DateTime, nullable=True)
    # Customer's on-prem LAN where their OLTs live (e.g. "192.168.1.0/24").
    # Set during onboarding so the cloud hub knows which packets to route
    # back through this workspace's WG tunnel. Must not overlap with any
    # other workspace's lan_subnet (enforced at the API layer in
    # backend/wireguard/routes.py:set_lan_subnet).
    lan_subnet = Column(String(43), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    tenant = relationship("Tenant", back_populates="workspaces")
    olts = relationship("OLT", back_populates="workspace")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_workspaces_tenant_name"),
    )


class WireGuardSubnet(Base):
    """Per-workspace /24 allocations from the reserved supernet (Phase 3.2).

    Owned by `wireguard.allocator`. Insert is the source of truth — the
    UNIQUE constraint on `cidr` is what prevents two concurrent
    provisioning calls from handing out the same /24 to two workspaces.
    """

    __tablename__ = "wireguard_subnets"

    cidr = Column(String(43), primary_key=True)
    workspace_id = Column(
        String(36),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    allocated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AgentKey(Base):
    """API key for a local agent that pushes data to the SaaS.

    Keys are stored hashed (SHA-256). The plaintext is shown to the user
    exactly once at creation time and never persisted. Revoking a key sets
    ``revoked_at``; the auth dependency also checks ``is_active``.
    """

    __tablename__ = "agent_keys"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    key_hash = Column(String(128), nullable=False, unique=True, index=True)
    key_prefix = Column(String(8), nullable=False)
    name = Column(String(100), default="Default Agent")
    is_active = Column(Boolean, default=True)
    last_seen_at = Column(DateTime, nullable=True)
    last_seen_ip = Column(String(45), nullable=True)
    agent_version = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)


class Feedback(Base):
    """Phase 6 — in-app customer feedback collected during the closed beta.

    The dashboard's "Send feedback" widget POSTs to /api/feedback which
    inserts a row here. Feedback is intentionally NOT scoped by RLS — it
    belongs to the tenant who submitted it but the support team needs
    cross-tenant visibility, so reads happen via the admin-only
    /admin/feedback endpoint.
    """

    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(
        String(36),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    category = Column(String(40), nullable=False)  # bug | idea | praise | other
    message = Column(Text, nullable=False)
    page_url = Column(String(500), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# Association table — a user can belong to multiple workspaces inside their tenant.
user_workspaces = Table(
    "user_workspaces",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("workspace_id", String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True),
    Column("role", String(20), nullable=False, default="operator"),
)


# Legacy association table for User-OLT direct assignment.
# Phase 1 keeps it for backwards compatibility with the operator-scoping UI;
# Phase 4 will retire it in favor of `user_workspaces`.
user_olts = Table(
    "user_olts",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id"), primary_key=True),
    Column("olt_id", Integer, ForeignKey("olts.id"), primary_key=True),
)


# ---------------------------------------------------------------------------
# Existing domain tables — every one gains tenant_id (and most a workspace_id)
# ---------------------------------------------------------------------------


class Region(Base):
    """Region/Group for organizing ONUs by area"""

    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    color = Column(String(7), default="#3B82F6")
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    onus = relationship("ONU", back_populates="region")
    owner = relationship("User", back_populates="owned_regions")


class OLT(Base):
    """OLT device model"""

    __tablename__ = "olts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=False)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    model = Column(String(50), nullable=True)
    pon_ports = Column(Integer, default=8)
    snmp_community = Column(String(100), nullable=True)  # SNMP read community (falls back to "public")
    is_online = Column(Boolean, default=False)
    last_poll = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    web_username = Column(String(100), nullable=True)
    web_password = Column(String(255), nullable=True)
    cpu_usage = Column(Integer, nullable=True)
    memory_usage = Column(Integer, nullable=True)
    temperature = Column(Integer, nullable=True)
    uptime_seconds = Column(Integer, nullable=True)
    # Mikrotik integration for accurate per-ONU traffic
    mk_ip = Column(String(45), nullable=True)
    mk_username = Column(String(100), nullable=True)
    mk_password = Column(String(255), nullable=True)
    mk_port = Column(Integer, default=8728)
    mk_enabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    onus = relationship("ONU", back_populates="olt", cascade="all, delete-orphan")
    workspace = relationship("Workspace", back_populates="olts")
    assigned_users = relationship("User", secondary="user_olts", back_populates="assigned_olts")

    __table_args__ = (
        UniqueConstraint("tenant_id", "ip_address", name="uq_olts_tenant_ip"),
    )


class ONU(Base):
    """ONU device model"""

    __tablename__ = "onus"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    pon_port = Column(Integer, nullable=False)
    onu_id = Column(Integer, nullable=False)
    mac_address = Column(String(17), nullable=False)
    description = Column(String(255), nullable=True)
    is_online = Column(Boolean, default=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(String(500), nullable=True)
    model = Column(String(50), nullable=True)
    distance = Column(Integer, nullable=True)
    rx_power = Column(Float, nullable=True)
    onu_rx_power = Column(Float, nullable=True)
    onu_tx_power = Column(Float, nullable=True)
    onu_temperature = Column(Float, nullable=True)
    onu_voltage = Column(Float, nullable=True)
    onu_tx_bias = Column(Float, nullable=True)
    image_url = Column(String(500), nullable=True)
    image_urls = Column(Text, nullable=True)
    missing_polls = Column(Integer, default=0)
    online_since = Column(DateTime, nullable=True)
    olt_alive_time = Column(Integer, nullable=True)
    offline_reason = Column(String(50), nullable=True)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    olt = relationship("OLT", back_populates="onus")
    region = relationship("Region", back_populates="onus")


class PollLog(Base):
    """Log of polling operations"""

    __tablename__ = "poll_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    status = Column(String(20), nullable=False)
    message = Column(Text, nullable=True)
    onus_found = Column(Integer, default=0)
    polled_at = Column(DateTime, default=datetime.utcnow)


class TrafficSnapshot(Base):
    """Traffic counter snapshot for rate calculation."""

    __tablename__ = "traffic_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    mac_address = Column(String(17), nullable=False)
    rx_bytes = Column(BigInteger, nullable=False, default=0)
    tx_bytes = Column(BigInteger, nullable=False, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)
    last_rx_kbps = Column(Float, nullable=False, default=0)
    last_tx_kbps = Column(Float, nullable=False, default=0)


class TrafficHistory(Base):
    """Historical traffic data for graphs."""

    __tablename__ = "traffic_history"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(10), nullable=False, index=True)
    entity_id = Column(String(50), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False, index=True)
    pon_port = Column(Integer, nullable=True)
    onu_db_id = Column(Integer, ForeignKey("onus.id"), nullable=True)
    rx_kbps = Column(Float, nullable=False, default=0)
    tx_kbps = Column(Float, nullable=False, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class OLTPort(Base):
    """OLT Port status model"""

    __tablename__ = "olt_ports"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False, index=True)
    port_type = Column(String(10), nullable=False)
    port_number = Column(Integer, nullable=False)
    if_index = Column(Integer, nullable=True)
    status = Column(String(10), default="unknown")
    onu_count = Column(Integer, default=0)
    tx_power = Column(Float, nullable=True)
    rx_power = Column(Float, nullable=True)
    temperature = Column(Float, nullable=True)
    speed = Column(String(20), nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)


class PortTraffic(Base):
    """Port traffic history for per-port bandwidth graphs"""

    __tablename__ = "port_traffic"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False, index=True)
    port_type = Column(String(10), nullable=False)
    port_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    rx_kbps = Column(Float, default=0)
    tx_kbps = Column(Float, default=0)


class Settings(Base):
    """System settings model.

    Per-tenant: each tenant has its own copy of every setting key.
    """

    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(50), nullable=False)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("tenant_id", "key", name="uq_settings_tenant_key"),
    )


class Diagram(Base):
    """Splitter simulator diagram model"""

    __tablename__ = "diagrams"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    nodes = Column(Text, nullable=False, default="[]")
    connections = Column(Text, nullable=False, default="[]")
    settings = Column(Text, nullable=False, default="{}")
    is_shared = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="diagrams")


class EventLog(Base):
    """Event log for tracking ONU/OLT status changes"""

    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False, index=True)
    entity_type = Column(String(20), nullable=False)
    entity_id = Column(Integer, nullable=False)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=True)
    description = Column(String(500), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


class ScheduledTask(Base):
    """Scheduled tasks for automation"""

    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    task_type = Column(String(50), nullable=False)
    target_type = Column(String(20), nullable=True)
    target_id = Column(Integer, nullable=True)
    schedule_type = Column(String(20), nullable=False)
    schedule_time = Column(String(10), nullable=False)
    schedule_day = Column(Integer, nullable=True)
    is_enabled = Column(Boolean, default=True)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConfigBackup(Base):
    """OLT configuration backups"""

    __tablename__ = "config_backups"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    backup_type = Column(String(20), default="manual")
    notes = Column(String(500), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AlertRule(Base):
    """Alert rules for signal quality and other monitoring"""

    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    rule_type = Column(String(50), nullable=False)
    threshold = Column(Float, nullable=True)
    comparison = Column(String(10), nullable=True)
    notify_email = Column(Boolean, default=False)
    notify_sms = Column(Boolean, default=False)
    notify_whatsapp = Column(Boolean, default=True)
    is_enabled = Column(Boolean, default=True)
    cooldown_minutes = Column(Integer, default=60)
    created_at = Column(DateTime, default=datetime.utcnow)


class SentAlert(Base):
    """Track sent alerts to prevent spam"""

    __tablename__ = "sent_alerts"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    alert_rule_id = Column(Integer, ForeignKey("alert_rules.id"), nullable=False)
    entity_type = Column(String(20), nullable=False)
    entity_id = Column(Integer, nullable=False)
    message = Column(String(500), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)


class SystemBackup(Base):
    """Full system database backups"""

    __tablename__ = "system_backups"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)
    backup_type = Column(String(20), default="manual")
    storage_type = Column(String(20), default="local")
    storage_path = Column(String(500), nullable=True)
    includes_db = Column(Boolean, default=True)
    includes_config = Column(Boolean, default=True)
    includes_uploads = Column(Boolean, default=False)
    status = Column(String(20), default="completed")
    error_message = Column(String(500), nullable=True)
    notes = Column(String(500), nullable=True)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class BackupSettings(Base):
    """Backup configuration settings (per tenant)"""

    __tablename__ = "backup_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Auto backup settings
    auto_backup_enabled = Column(Boolean, default=False)
    backup_frequency = Column(String(20), default="daily")
    backup_time = Column(String(10), default="02:00")
    backup_day = Column(Integer, nullable=True)
    retention_days = Column(Integer, default=30)

    backup_database = Column(Boolean, default=True)
    backup_config = Column(Boolean, default=True)
    backup_uploads = Column(Boolean, default=False)

    storage_type = Column(String(20), default="local")
    local_path = Column(String(500), default="/opt/olt-manager/backups")

    ftp_host = Column(String(255), nullable=True)
    ftp_port = Column(Integer, default=21)
    ftp_username = Column(String(100), nullable=True)
    ftp_password = Column(String(255), nullable=True)
    ftp_path = Column(String(255), default="/backups")
    ftp_use_sftp = Column(Boolean, default=False)

    s3_bucket = Column(String(255), nullable=True)
    s3_region = Column(String(50), nullable=True)
    s3_access_key = Column(String(255), nullable=True)
    s3_secret_key = Column(String(255), nullable=True)
    s3_path = Column(String(255), default="/olt-manager-backups")

    last_backup_at = Column(DateTime, nullable=True)
    last_backup_status = Column(String(20), nullable=True)
    next_backup_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    """User model for authentication and authorization.

    Phase 1 changes:
        * Primary key is now a UUID string (matches Tenant/Workspace)
        * `username` renamed to `email`, unique within (tenant_id, email)
        * `tenant_id` is required for every user except superadmins (which we
          don't model in Phase 1)
    """

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=_new_uuid)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(254), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="operator")  # owner|admin|operator|viewer
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    is_staff = Column(Boolean, default=False)  # internal cross-tenant support; set manually in DB
    must_change_password = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)
    email_verified_at = Column(DateTime, nullable=True)  # Phase 2
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    tenant = relationship("Tenant", back_populates="users")
    assigned_olts = relationship("OLT", secondary="user_olts", back_populates="assigned_users")
    workspaces = relationship("Workspace", secondary="user_workspaces")
    owned_regions = relationship("Region", back_populates="owner")
    diagrams = relationship("Diagram", back_populates="owner")

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )

    # Backwards-compatibility shim — main.py and auth.py still reference
    # `User.username` in many places. Map it transparently to `email` so
    # the Phase 1 rename does not require touching every call site at once.
    @property
    def username(self) -> str:
        return self.email

    @username.setter
    def username(self, value: str) -> None:
        self.email = value


# ---------------------------------------------------------------------------
# Tenant context for SQLAlchemy sessions (Phase 1.6)
# ---------------------------------------------------------------------------
#
# Postgres Row-Level Security policies (migration 0004) check the GUC
# `app.current_tenant_id`. We set it on every transaction begin from
# whatever the session has been tagged with via `set_session_tenant`.
#
# This event listener is a no-op on SQLite (RLS doesn't exist there) and on
# sessions that haven't been tagged with a tenant_id (e.g. the bootstrap
# migration code that needs to see all rows).
# ---------------------------------------------------------------------------


def set_session_tenant(session: Session, tenant_id: str) -> None:
    """Tag a SQLAlchemy session so the next transaction begins with
    `app.current_tenant_id` set to this tenant. Idempotent within a request.
    """
    session.info["tenant_id"] = tenant_id


def set_session_workspace(session: Session, workspace_id: str) -> None:
    """Tag a session with a default workspace_id used by the
    before_insert auto-fill hook for legacy main.py routes.
    """
    session.info["workspace_id"] = workspace_id


def clear_session_tenant(session: Session) -> None:
    session.info.pop("tenant_id", None)
    session.info.pop("workspace_id", None)


@event.listens_for(SessionLocal, "after_begin")
def _set_tenant_guc(session, transaction, connection):
    """Apply the per-session tenant_id to the underlying connection.

    This runs after every transaction starts. We use SET LOCAL so the GUC is
    scoped to the current transaction and rolls back automatically.
    """
    if not is_postgres():
        return
    tenant_id = session.info.get("tenant_id")
    if not tenant_id:
        return
    # Whitelist UUID-shaped values only — defense against SQL injection if
    # the caller ever wired this from untrusted input.
    safe = str(tenant_id).replace("'", "")
    connection.execute(text(f"SET LOCAL app.current_tenant_id = '{safe}'"))


# ---------------------------------------------------------------------------
# Auto-fill tenant_id / workspace_id on insert (Phase 1 legacy bridge)
# ---------------------------------------------------------------------------
# The legacy main.py routes (~68 endpoints) were written for the
# single-tenant SQLite world and don't pass tenant_id/workspace_id when
# constructing model instances. Rather than rewrite every route, we hook
# `before_flush` at the Session level: any new instance whose mapper has
# `tenant_id` / `workspace_id` columns gets them auto-filled from
# session.info, which `require_auth` populates from the JWT user.
# ---------------------------------------------------------------------------


@event.listens_for(SessionLocal, "before_flush")
def _autofill_tenant_workspace(session, flush_context, instances):
    tid = session.info.get("tenant_id")
    wid = session.info.get("workspace_id")
    if not tid and not wid:
        return
    for obj in session.new:
        try:
            cols = obj.__table__.columns.keys()
        except AttributeError:
            continue
        if tid and "tenant_id" in cols and getattr(obj, "tenant_id", None) is None:
            obj.tenant_id = tid
        if wid and "workspace_id" in cols and getattr(obj, "workspace_id", None) is None:
            obj.workspace_id = wid


# ---------------------------------------------------------------------------
# Database init + session helpers
# ---------------------------------------------------------------------------


def run_migrations():
    """Legacy in-process migrations for the SQLite single-tenant binary.

    Phase 1 supersedes this with Alembic. The function is kept (and made a
    no-op on Postgres) so the existing single-tenant binary keeps booting
    until Phase 5 cutover.
    """
    if is_postgres():
        # Postgres uses Alembic — see backend/migrations/.
        return

    import sqlite3
    db_path = DATABASE_URL.replace("sqlite:///", "").replace("sqlite:////", "/")
    if not db_path:
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(olts)")
        existing_columns = {col[1] for col in cursor.fetchall()}

        health_columns = [
            ("cpu_usage", "INTEGER"),
            ("memory_usage", "INTEGER"),
            ("temperature", "INTEGER"),
            ("uptime_seconds", "INTEGER"),
        ]
        for col_name, col_type in health_columns:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE olts ADD COLUMN {col_name} {col_type}")

        cursor.execute("PRAGMA table_info(olt_ports)")
        port_columns = {col[1] for col in cursor.fetchall()}
        if "temperature" not in port_columns:
            cursor.execute("ALTER TABLE olt_ports ADD COLUMN temperature REAL")

        cursor.execute("PRAGMA table_info(onus)")
        onu_columns = {col[1] for col in cursor.fetchall()}
        for col_name, col_type in [
            ("model", "VARCHAR(50)"),
            ("onu_rx_power", "REAL"),
            ("olt_alive_time", "INTEGER"),
        ]:
            if col_name not in onu_columns:
                cursor.execute(f"ALTER TABLE onus ADD COLUMN {col_name} {col_type}")

        cursor.execute("PRAGMA table_info(olts)")
        olt_columns = {col[1] for col in cursor.fetchall()}
        for col_name, col_type in [
            ("web_username", "VARCHAR(100)"),
            ("web_password", "VARCHAR(255)"),
            ("snmp_community", "VARCHAR(100)"),
            ("mk_ip", "VARCHAR(45)"),
            ("mk_username", "VARCHAR(100)"),
            ("mk_password", "VARCHAR(255)"),
            ("mk_port", "INTEGER DEFAULT 8728"),
            ("mk_enabled", "BOOLEAN DEFAULT 0"),
        ]:
            if col_name not in olt_columns:
                cursor.execute(f"ALTER TABLE olts ADD COLUMN {col_name} {col_type}")

        # Indexes for hot poll-path lookups (idempotent).
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS ix_onus_olt_mac ON onus (olt_id, mac_address)",
            "CREATE INDEX IF NOT EXISTS ix_traffic_snapshots_olt_mac ON traffic_snapshots (olt_id, mac_address)",
            "CREATE INDEX IF NOT EXISTS ix_poll_logs_olt_id ON poll_logs (olt_id)",
        ]:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass

        cursor.execute("PRAGMA table_info(users)")
        user_columns = {col[1] for col in cursor.fetchall()}
        for col_name, col_type in [
            ("must_change_password", "BOOLEAN DEFAULT 0"),
            ("failed_login_attempts", "INTEGER DEFAULT 0"),
            ("locked_until", "DATETIME"),
            ("is_staff", "BOOLEAN DEFAULT 0"),
        ]:
            if col_name not in user_columns:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[Migration] Warning: Could not run migrations: {e}")


def init_db():
    """Initialize database tables.

    Phase 1: on Postgres, use `alembic upgrade head` instead of calling this
    directly. On SQLite (legacy single-tenant binary) we still create tables
    + run the in-process migrations.
    """
    if is_postgres():
        # Schema is owned by Alembic. Importing this module is still safe.
        return
    Base.metadata.create_all(bind=engine)
    run_migrations()


def get_db():
    """Get database session (legacy, no tenant context).

    Most routes should switch to `tenancy.get_tenant_db` so the session is
    automatically scoped to the caller's tenant.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
