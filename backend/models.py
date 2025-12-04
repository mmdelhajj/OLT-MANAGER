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
    # Optical diagnostics (from SNMP)
    distance = Column(Integer, nullable=True)  # Distance in meters
    rx_power = Column(Float, nullable=True)  # RX Power in dBm (OLT receiving from ONU)
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


class Settings(Base):
    """System settings model"""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), nullable=False, unique=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
