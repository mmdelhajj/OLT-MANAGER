"""Pydantic models for the agent -> SaaS wire format.

This is a standalone copy of backend/agent_payload.py so the agent package
can be distributed without the full backend.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ONUPayload(BaseModel):
    pon_port: int
    onu_id: int
    mac_address: str
    is_online: bool = False
    description: Optional[str] = None
    model: Optional[str] = None
    distance: Optional[int] = None
    rx_power: Optional[float] = None
    onu_rx_power: Optional[float] = None
    onu_tx_power: Optional[float] = None
    onu_temperature: Optional[float] = None
    onu_voltage: Optional[float] = None
    onu_tx_bias: Optional[float] = None
    rx_kbps: float = 0
    tx_kbps: float = 0
    alive_time_seconds: Optional[int] = None
    offline_reason: Optional[str] = None


class PortTrafficPayload(BaseModel):
    if_index: int
    port_type: str = "ge"
    port_number: int = 0
    rx_kbps: float = 0
    tx_kbps: float = 0


class OLTPayload(BaseModel):
    ip_address: str
    name: Optional[str] = None
    model: Optional[str] = None
    is_online: bool = True
    health: Dict[str, Any] = Field(default_factory=dict)
    onus: List[ONUPayload] = Field(default_factory=list)
    port_traffic: List[PortTrafficPayload] = Field(default_factory=list)


class AgentPayload(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_version: Optional[str] = None
    olts: List[OLTPayload] = Field(default_factory=list)
