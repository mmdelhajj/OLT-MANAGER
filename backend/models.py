"""Database models for OLT Manager"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Table, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Association table for User-OLT many-to-many relationship
user_olts = Table(
    'user_olts',
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id'), primary_key=True),
    Column('olt_id', Integer, ForeignKey('olts.id'), primary_key=True)
)


class Region(Base):
    """Region/Group for organizing ONUs by area"""
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    color = Column(String(7), default="#3B82F6")  # Hex color for UI
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL = admin-created (visible to all)
    latitude = Column(Float, nullable=True)  # GPS latitude
    longitude = Column(Float, nullable=True)  # GPS longitude
    address = Column(String(500), nullable=True)  # Optional address description
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    onus = relationship("ONU", back_populates="region")
    owner = relationship("User", back_populates="owned_regions")


class OLT(Base):
    """OLT device model"""
    __tablename__ = "olts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=False, unique=True)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    model = Column(String(50), nullable=True)  # V1600D8, V1601E04, etc.
    pon_ports = Column(Integer, default=8)
    is_online = Column(Boolean, default=False)
    last_poll = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    # Web interface credentials (for ONU OPM data scraping)
    web_username = Column(String(100), nullable=True)  # Web login username (default: admin)
    web_password = Column(String(255), nullable=True)  # Web login password
    # Health metrics (from SNMP polling)
    cpu_usage = Column(Integer, nullable=True)  # CPU usage percentage (0-100)
    memory_usage = Column(Integer, nullable=True)  # Memory usage percentage (0-100)
    temperature = Column(Integer, nullable=True)  # Temperature in Celsius
    uptime_seconds = Column(Integer, nullable=True)  # Uptime in seconds
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    onus = relationship("ONU", back_populates="olt", cascade="all, delete-orphan")
    assigned_users = relationship("User", secondary="user_olts", back_populates="assigned_olts")


class ONU(Base):
    """ONU device model"""
    __tablename__ = "onus"

    id = Column(Integer, primary_key=True, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=True)
    pon_port = Column(Integer, nullable=False)
    onu_id = Column(Integer, nullable=False)
    mac_address = Column(String(17), nullable=False)
    description = Column(String(255), nullable=True)  # Customer name
    is_online = Column(Boolean, default=True)
    latitude = Column(Float, nullable=True)  # GPS latitude for customer location
    longitude = Column(Float, nullable=True)  # GPS longitude for customer location
    address = Column(String(500), nullable=True)  # Customer address
    # ONU Hardware info (from SNMP)
    model = Column(String(50), nullable=True)  # ONU model e.g. "V2801S", "V2801RD", "HG325AX15"
    # Optical diagnostics (from SNMP)
    distance = Column(Integer, nullable=True)  # Distance in meters
    rx_power = Column(Float, nullable=True)  # RX Power in dBm (OLT receiving from ONU) - what OLT measures ~-26 dBm
    # ONU self-reported optical data (from web scraping) - what customer sees
    onu_rx_power = Column(Float, nullable=True)  # ONU RX Power ~-13 dBm
    onu_tx_power = Column(Float, nullable=True)  # ONU TX Power in dBm
    onu_temperature = Column(Float, nullable=True)  # ONU Temperature in Celsius
    onu_voltage = Column(Float, nullable=True)  # ONU Supply Voltage in Volts
    onu_tx_bias = Column(Float, nullable=True)  # ONU TX Bias Current in mA
    image_url = Column(String(500), nullable=True)  # Building/location image URL (legacy - single image)
    image_urls = Column(Text, nullable=True)  # JSON array of up to 3 image URLs
    missing_polls = Column(Integer, default=0)  # Counter for consecutive polls where ONU not found (for auto-delete)
    last_seen = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    olt = relationship("OLT", back_populates="onus")
    region = relationship("Region", back_populates="onus")

    class Config:
        # Unique constraint on olt_id + pon_port + onu_id
        pass


class PollLog(Base):
    """Log of polling operations"""
    __tablename__ = "poll_logs"

    id = Column(Integer, primary_key=True, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    status = Column(String(20), nullable=False)  # success, error
    message = Column(Text, nullable=True)
    onus_found = Column(Integer, default=0)
    polled_at = Column(DateTime, default=datetime.utcnow)


class TrafficSnapshot(Base):
    """Traffic counter snapshot for rate calculation.
    Stores the last known traffic counters per OLT.
    Used to calculate bandwidth by comparing with new counters.
    """
    __tablename__ = "traffic_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False)
    mac_address = Column(String(17), nullable=False)  # ONU MAC address
    rx_bytes = Column(Integer, nullable=False, default=0)  # 64-bit counter (use BigInteger in production)
    tx_bytes = Column(Integer, nullable=False, default=0)  # 64-bit counter
    timestamp = Column(DateTime, default=datetime.utcnow)
    # Store last calculated rates to avoid jumping to 0
    last_rx_kbps = Column(Float, nullable=False, default=0)
    last_tx_kbps = Column(Float, nullable=False, default=0)

    class Meta:
        # Index for fast lookup by OLT
        pass


class TrafficHistory(Base):
    """Historical traffic data for graphs.
    Stores traffic rates (kbps) at regular intervals for ONUs, PON ports, and OLTs.
    """
    __tablename__ = "traffic_history"

    id = Column(Integer, primary_key=True, index=True)
    # Type: 'onu', 'pon', 'olt'
    entity_type = Column(String(10), nullable=False, index=True)
    # For ONU: onu_id, For PON: "olt_id:pon_port", For OLT: olt_id
    entity_id = Column(String(50), nullable=False, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False, index=True)
    pon_port = Column(Integer, nullable=True)  # Only for PON and ONU types
    onu_db_id = Column(Integer, ForeignKey("onus.id"), nullable=True)  # Only for ONU type
    rx_kbps = Column(Float, nullable=False, default=0)  # Download rate in kbps
    tx_kbps = Column(Float, nullable=False, default=0)  # Upload rate in kbps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class OLTPort(Base):
    """OLT Port status model - tracks individual PON and SFP ports"""
    __tablename__ = "olt_ports"

    id = Column(Integer, primary_key=True, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False, index=True)
    port_type = Column(String(10), nullable=False)  # 'pon', 'ge', 'xge'
    port_number = Column(Integer, nullable=False)
    if_index = Column(Integer, nullable=True)  # SNMP interface index
    status = Column(String(10), default='unknown')  # 'up', 'down', 'unknown'
    onu_count = Column(Integer, default=0)  # For PON ports
    tx_power = Column(Float, nullable=True)  # Optical TX power in dBm
    rx_power = Column(Float, nullable=True)  # Optical RX power in dBm
    temperature = Column(Float, nullable=True)  # PON transceiver temperature in Celsius
    speed = Column(String(20), nullable=True)  # Port speed e.g. "1G", "10G"
    last_updated = Column(DateTime, default=datetime.utcnow)

    # Unique constraint
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class PortTraffic(Base):
    """Port traffic history for per-port bandwidth graphs"""
    __tablename__ = "port_traffic"

    id = Column(Integer, primary_key=True, index=True)
    olt_id = Column(Integer, ForeignKey("olts.id"), nullable=False, index=True)
    port_type = Column(String(10), nullable=False)  # 'pon', 'ge', 'xge'
    port_number = Column(Integer, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    rx_kbps = Column(Float, default=0)  # Download rate
    tx_kbps = Column(Float, default=0)  # Upload rate


class Settings(Base):
    """System settings model"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, unique=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Diagram(Base):
    """Splitter simulator diagram model for storing network topology designs"""
    __tablename__ = "diagrams"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String(255), nullable=False)
    nodes = Column(Text, nullable=False, default="[]")  # JSON string of nodes
    connections = Column(Text, nullable=False, default="[]")  # JSON string of connections
    settings = Column(Text, nullable=False, default="{}")  # JSON string of settings (oltPower, onuSensitivity)
    is_shared = Column(Boolean, default=False)  # If true, all users can view
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    owner = relationship("User", back_populates="diagrams")


class User(Base):
    """User model for authentication and authorization"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="operator")  # admin, operator
    full_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    # Relationship - OLTs assigned to this user (for operators)
    assigned_olts = relationship("OLT", secondary="user_olts", back_populates="assigned_users")
    # Regions owned by this user
    owned_regions = relationship("Region", back_populates="owner")
    # Diagrams owned by this user
    diagrams = relationship("Diagram", back_populates="owner")


def run_migrations():
    """Run database migrations for schema updates"""
    import sqlite3
    from config import DATABASE_URL

    # Extract database path from URL
    if 'sqlite' in DATABASE_URL:
        db_path = DATABASE_URL.replace('sqlite:///', '')

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Get existing columns in olts table
            cursor.execute("PRAGMA table_info(olts)")
            existing_columns = {col[1] for col in cursor.fetchall()}

            # Migrations for OLT health metrics (v1.2.0)
            health_columns = [
                ('cpu_usage', 'INTEGER'),
                ('memory_usage', 'INTEGER'),
                ('temperature', 'INTEGER'),
                ('uptime_seconds', 'INTEGER')
            ]

            for col_name, col_type in health_columns:
                if col_name not in existing_columns:
                    print(f"[Migration] Adding column {col_name} to olts table...")
                    cursor.execute(f"ALTER TABLE olts ADD COLUMN {col_name} {col_type}")

            # Migrations for OLTPort temperature column (v1.3.0)
            cursor.execute("PRAGMA table_info(olt_ports)")
            port_columns = {col[1] for col in cursor.fetchall()}
            if 'temperature' not in port_columns:
                print("[Migration] Adding temperature column to olt_ports table...")
                cursor.execute("ALTER TABLE olt_ports ADD COLUMN temperature REAL")

            # Migrations for ONU model column (v1.4.0)
            cursor.execute("PRAGMA table_info(onus)")
            onu_columns = {col[1] for col in cursor.fetchall()}
            if 'model' not in onu_columns:
                print("[Migration] Adding model column to onus table...")
                cursor.execute("ALTER TABLE onus ADD COLUMN model VARCHAR(50)")

            # Migration for ONU RX Power (v1.5.0) - ONU self-reported RX power from web scraping
            if 'onu_rx_power' not in onu_columns:
                print("[Migration] Adding onu_rx_power column to onus table...")
                cursor.execute("ALTER TABLE onus ADD COLUMN onu_rx_power REAL")

            # Migration for OLT web credentials (v1.5.0) - for web scraping OPM data
            cursor.execute("PRAGMA table_info(olts)")
            olt_columns = {col[1] for col in cursor.fetchall()}
            if 'web_username' not in olt_columns:
                print("[Migration] Adding web_username column to olts table...")
                cursor.execute("ALTER TABLE olts ADD COLUMN web_username VARCHAR(100)")
            if 'web_password' not in olt_columns:
                print("[Migration] Adding web_password column to olts table...")
                cursor.execute("ALTER TABLE olts ADD COLUMN web_password VARCHAR(255)")

            conn.commit()
            conn.close()
            print("[Migration] Database migrations completed successfully")
        except Exception as e:
            print(f"[Migration] Warning: Could not run migrations: {e}")


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    # Run migrations for existing databases
    run_migrations()


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
