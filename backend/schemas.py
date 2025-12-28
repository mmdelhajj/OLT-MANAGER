"""Pydantic schemas for API request/response"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# OLT Schemas
class OLTBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    ip_address: str = Field(..., pattern=r'^(\d{1,3}\.){3}\d{1,3}$')
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)
    model: Optional[str] = Field(None, max_length=50)
    pon_ports: int = Field(default=8, ge=1, le=16)


class OLTCreate(OLTBase):
    pass


class OLTUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    username: Optional[str] = Field(None, min_length=1, max_length=100)
    password: Optional[str] = Field(None, min_length=1, max_length=255)
    model: Optional[str] = Field(None, max_length=50)
    pon_ports: Optional[int] = Field(None, ge=1, le=16)


class OLTResponse(BaseModel):
    id: int
    name: str
    ip_address: str
    model: Optional[str]
    pon_ports: int
    is_online: bool
    last_poll: Optional[datetime]
    last_error: Optional[str]
    onu_count: int = 0
    online_onu_count: int = 0
    # Health metrics
    cpu_usage: Optional[int] = None  # CPU usage percentage (0-100)
    memory_usage: Optional[int] = None  # Memory usage percentage (0-100)
    temperature: Optional[int] = None  # Temperature in Celsius
    uptime_seconds: Optional[int] = None  # Uptime in seconds
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OLTListResponse(BaseModel):
    olts: List[OLTResponse]
    total: int


# Region Schemas
class RegionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    color: str = Field(default="#3B82F6", pattern=r'^#[0-9A-Fa-f]{6}$')
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    address: Optional[str] = Field(None, max_length=500)


class RegionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    address: Optional[str] = Field(None, max_length=500)


class RegionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    owner_id: Optional[int] = None
    owner_name: Optional[str] = None  # For display purposes
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    google_maps_url: Optional[str] = None  # Generated URL for Google Maps
    onu_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class RegionListResponse(BaseModel):
    regions: List[RegionResponse]
    total: int


# ONU Schemas
class ONUUpdate(BaseModel):
    description: Optional[str] = Field(None, max_length=255)
    region_id: Optional[int] = None
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    address: Optional[str] = Field(None, max_length=500)
    image_url: Optional[str] = Field(None, max_length=500)


class ONUResponse(BaseModel):
    id: int
    olt_id: int
    olt_name: str
    region_id: Optional[int]
    region_name: Optional[str]
    region_color: Optional[str] = None
    pon_port: int
    onu_id: int
    mac_address: str
    description: Optional[str]
    is_online: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    google_maps_url: Optional[str] = None
    distance: Optional[int] = None  # Distance in meters
    rx_power: Optional[float] = None  # RX Power in dBm (OLT-measured)
    onu_rx_power: Optional[float] = None  # ONU self-reported RX Power in dBm
    onu_tx_power: Optional[float] = None  # ONU self-reported TX Power in dBm
    onu_temperature: Optional[float] = None  # ONU Temperature in Celsius
    onu_voltage: Optional[float] = None  # ONU Supply Voltage in Volts
    onu_tx_bias: Optional[float] = None  # ONU TX Bias Current in mA
    model: Optional[str] = None  # ONU model e.g. "V2801S", "V2801RD", "HG325AX15"
    image_url: Optional[str] = None  # Building/location image (legacy - single)
    image_urls: Optional[List[str]] = None  # Multiple building/location images (up to 3)
    last_seen: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class ONUListResponse(BaseModel):
    onus: List[ONUResponse]
    total: int


# Dashboard Stats
class DashboardStats(BaseModel):
    total_olts: int
    online_olts: int
    offline_olts: int
    total_onus: int
    online_onus: int
    offline_onus: int


# Poll Result
class PollResult(BaseModel):
    olt_id: int
    olt_name: str
    success: bool
    message: str
    onus_found: int


# User Schemas
class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=255)


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=4, max_length=255)
    role: str = Field(default="operator", pattern=r'^(admin|operator)$')
    full_name: Optional[str] = Field(None, max_length=100)
    assigned_olt_ids: Optional[List[int]] = Field(default=[])


class UserUpdate(BaseModel):
    password: Optional[str] = Field(None, min_length=4, max_length=255)
    role: Optional[str] = Field(None, pattern=r'^(admin|operator)$')
    full_name: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None
    assigned_olt_ids: Optional[List[int]] = None


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    assigned_olt_ids: List[int] = []

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    users: List[UserResponse]
    total: int


class LoginResponse(BaseModel):
    token: str
    user: UserResponse
    must_change_password: bool = False


# Diagram Schemas
class DiagramCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    nodes: str = Field(default="[]")  # JSON string of nodes
    connections: str = Field(default="[]")  # JSON string of connections
    settings: str = Field(default="{}")  # JSON string of settings
    is_shared: bool = Field(default=False)


class DiagramUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    nodes: Optional[str] = None  # JSON string of nodes
    connections: Optional[str] = None  # JSON string of connections
    settings: Optional[str] = None  # JSON string of settings
    is_shared: Optional[bool] = None


class DiagramResponse(BaseModel):
    id: int
    owner_id: int
    owner_name: Optional[str] = None
    name: str
    nodes: str  # JSON string
    connections: str  # JSON string
    settings: str  # JSON string
    is_shared: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DiagramListResponse(BaseModel):
    diagrams: List[DiagramResponse]
    total: int
