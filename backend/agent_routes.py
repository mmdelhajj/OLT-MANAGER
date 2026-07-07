"""Agent API routes for the SaaS local-agent system.

Endpoints for:
    * Agent key management (JWT-authenticated, admin only)
    * Data ingest (agent-key authenticated)
    * Heartbeat (agent-key authenticated)
    * Agent connection status (JWT-authenticated)
"""
from __future__ import annotations

import hashlib
import logging
import secrets
import time
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent_payload import AgentPayload
from auth import require_admin, require_auth
from models import (
    AgentKey,
    OLT,
    ONU,
    PortTraffic,
    SessionLocal,
    Tenant,
    TrafficHistory,
    User,
    set_session_tenant,
    set_session_workspace,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Rate limiting: track last ingest timestamp per key id
_last_ingest: dict[str, float] = {}
INGEST_MIN_INTERVAL = 10  # seconds
MAX_PAYLOAD_ONUS = 5000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hash_key(raw_key: str) -> str:
    """SHA-256 hash of a plaintext API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Agent key authentication dependency
# ---------------------------------------------------------------------------


def require_agent_key(
    request: Request,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(_db),
) -> AgentKey:
    """Validate a Bearer agent key and return the AgentKey row.

    Also tags the DB session with the key's tenant_id/workspace_id so that
    subsequent queries respect RLS and auto-fill hooks work.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing agent key")

    raw_key = authorization[7:]
    if not raw_key.startswith("agk_"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid key format")

    key_hash = _hash_key(raw_key)
    agent_key = db.query(AgentKey).filter(
        AgentKey.key_hash == key_hash,
        AgentKey.is_active == True,
        AgentKey.revoked_at == None,
    ).first()

    if not agent_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked agent key")

    # Tag session for RLS and auto-fill
    set_session_tenant(db, agent_key.tenant_id)
    set_session_workspace(db, agent_key.workspace_id)

    # Postgres RLS: set GUC for this transaction
    from models import is_postgres
    from sqlalchemy import text as _sql_text
    if is_postgres():
        safe_tid = str(agent_key.tenant_id).replace("'", "")
        db.execute(_sql_text(f"SET LOCAL app.current_tenant_id = '{safe_tid}'"))

    return agent_key


# ---------------------------------------------------------------------------
# Key management endpoints (JWT admin)
# ---------------------------------------------------------------------------


class CreateKeyRequest(BaseModel):
    name: str = "Default Agent"
    workspace_id: Optional[str] = None


class KeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    workspace_id: str
    is_active: bool
    last_seen_at: Optional[datetime] = None
    last_seen_ip: Optional[str] = None
    agent_version: Optional[str] = None
    created_at: datetime


class CreateKeyResponse(KeyResponse):
    raw_key: str  # shown once


@router.post("/keys", response_model=CreateKeyResponse, status_code=status.HTTP_201_CREATED)
def create_agent_key(
    payload: CreateKeyRequest,
    user: User = Depends(require_admin),
    db: Session = Depends(_db),
):
    """Generate a new agent API key. The plaintext is returned once."""
    from models import Workspace

    # Resolve workspace
    workspace_id = payload.workspace_id
    if not workspace_id:
        ws = db.query(Workspace).filter(Workspace.tenant_id == user.tenant_id).first()
        if not ws:
            raise HTTPException(status_code=400, detail="No workspace found")
        workspace_id = ws.id
    else:
        ws = db.query(Workspace).filter(
            Workspace.id == workspace_id,
            Workspace.tenant_id == user.tenant_id,
        ).first()
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found")

    raw_key = "agk_" + secrets.token_hex(24)
    key_hash = _hash_key(raw_key)

    agent_key = AgentKey(
        tenant_id=user.tenant_id,
        workspace_id=workspace_id,
        key_hash=key_hash,
        key_prefix=raw_key[:8],
        name=payload.name,
    )
    db.add(agent_key)
    db.commit()
    db.refresh(agent_key)

    return CreateKeyResponse(
        id=agent_key.id,
        name=agent_key.name,
        key_prefix=agent_key.key_prefix,
        workspace_id=agent_key.workspace_id,
        is_active=agent_key.is_active,
        last_seen_at=agent_key.last_seen_at,
        last_seen_ip=agent_key.last_seen_ip,
        agent_version=agent_key.agent_version,
        created_at=agent_key.created_at,
        raw_key=raw_key,
    )


@router.get("/keys", response_model=list[KeyResponse])
def list_agent_keys(
    user: User = Depends(require_admin),
    db: Session = Depends(_db),
):
    """List all agent keys for this tenant."""
    keys = db.query(AgentKey).filter(AgentKey.tenant_id == user.tenant_id).all()
    return [
        KeyResponse(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            workspace_id=k.workspace_id,
            is_active=k.is_active,
            last_seen_at=k.last_seen_at,
            last_seen_ip=k.last_seen_ip,
            agent_version=k.agent_version,
            created_at=k.created_at,
        )
        for k in keys
    ]


@router.delete("/keys/{key_id}")
def revoke_agent_key(
    key_id: str,
    user: User = Depends(require_admin),
    db: Session = Depends(_db),
):
    """Revoke an agent key."""
    agent_key = db.query(AgentKey).filter(
        AgentKey.id == key_id,
        AgentKey.tenant_id == user.tenant_id,
    ).first()
    if not agent_key:
        raise HTTPException(status_code=404, detail="Key not found")

    agent_key.is_active = False
    agent_key.revoked_at = datetime.utcnow()
    db.commit()
    return {"status": "revoked"}


# ---------------------------------------------------------------------------
# Agent status (JWT)
# ---------------------------------------------------------------------------


@router.get("/status")
def agent_status(
    user: User = Depends(require_auth),
    db: Session = Depends(_db),
):
    """Return agent connection status for the tenant's workspaces."""
    keys = db.query(AgentKey).filter(
        AgentKey.tenant_id == user.tenant_id,
        AgentKey.is_active == True,
    ).all()

    now = datetime.utcnow()
    result = []
    for k in keys:
        is_connected = (
            k.last_seen_at is not None
            and (now - k.last_seen_at).total_seconds() < 120
        )
        result.append({
            "key_id": k.id,
            "workspace_id": k.workspace_id,
            "name": k.name,
            "is_connected": is_connected,
            "last_seen_at": k.last_seen_at.isoformat() if k.last_seen_at else None,
            "agent_version": k.agent_version,
        })
    return result


# ---------------------------------------------------------------------------
# Heartbeat (agent key)
# ---------------------------------------------------------------------------


@router.post("/heartbeat")
def heartbeat(
    request: Request,
    agent_key: AgentKey = Depends(require_agent_key),
    db: Session = Depends(_db),
):
    """Lightweight alive ping from the agent."""
    agent_key.last_seen_at = datetime.utcnow()
    agent_key.last_seen_ip = request.client.host if request.client else None
    db.commit()
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Ingest endpoint (agent key) — the main data path
# ---------------------------------------------------------------------------


@router.post("/ingest")
def ingest(
    payload: AgentPayload,
    request: Request,
    agent_key: AgentKey = Depends(require_agent_key),
    db: Session = Depends(_db),
):
    """Receive polled data from a local agent.

    Mirrors the logic in poll_all_olts but receives data instead of polling.
    """
    # Rate limit
    now = time.time()
    last = _last_ingest.get(agent_key.id, 0)
    if now - last < INGEST_MIN_INTERVAL:
        raise HTTPException(status_code=429, detail="Too frequent — wait 10s between pushes")
    _last_ingest[agent_key.id] = now

    tenant_id = agent_key.tenant_id
    workspace_id = agent_key.workspace_id
    onus_processed = 0
    # Use the agent's measured timestamp so history points land at measurement
    # time (not push-receipt time, which skews the graph x-axis on delays/retries).
    # Clamp to a sane window vs the server clock to guard a badly-skewed agent.
    current_time = datetime.utcnow()
    try:
        agent_ts = getattr(payload, "timestamp", None)
        if agent_ts is not None and abs((current_time - agent_ts).total_seconds()) <= 3600:
            current_time = agent_ts
    except Exception:
        pass

    # Enforce the tenant's billing-plan limits on the agent path too (was
    # unchecked). Resolve once; skip creating rows past the limit instead of
    # 402-ing the whole batch (which would discard all the other data).
    from plans import get_plan
    _tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    _plan = get_plan(_tenant) if _tenant else None
    _onu_count = db.query(ONU).count() if _plan else 0  # RLS-scoped to tenant

    for olt_data in payload.olts:
        logger.info(f"[ingest] OLT {olt_data.ip_address} model={olt_data.model} "
                     f"online={olt_data.is_online} onus={len(olt_data.onus)}")
        # Find or create OLT by (tenant_id, ip_address)
        olt = db.query(OLT).filter(
            OLT.tenant_id == tenant_id,
            OLT.ip_address == olt_data.ip_address,
        ).first()

        if not olt:
            if _plan and db.query(OLT).count() >= _plan.max_olts:
                logger.warning(
                    f"[ingest] OLT plan limit ({_plan.max_olts}) reached for tenant "
                    f"{tenant_id}; skipping new OLT {olt_data.ip_address}"
                )
                continue
            olt = OLT(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                name=olt_data.name or olt_data.ip_address,
                ip_address=olt_data.ip_address,
                username="agent",
                password="agent-managed",
                model=olt_data.model,
            )
            db.add(olt)
            db.flush()

        # Update OLT fields
        # When agent can't reach the OLT (online=False, 0 ONUs), mark it
        # as "agent:unreachable" so the SaaS fallback loop knows to poll it
        # directly via WireGuard.  Don't overwrite is_online if SaaS
        # fallback already proved the OLT is reachable.
        agent_unreachable = (
            not olt_data.is_online and len(olt_data.onus) == 0
        )
        if agent_unreachable:
            if not olt.is_online:
                olt.is_online = False
            # Signal for the SaaS fallback polling loop
            olt.last_error = "agent:unreachable"
        else:
            olt.is_online = olt_data.is_online
            olt.last_error = None
        olt.last_poll = current_time
        if olt_data.model and not olt.model:
            olt.model = olt_data.model
        if olt_data.name and olt.name == olt.ip_address:
            olt.name = olt_data.name

        # Health metrics
        health = olt_data.health
        if health:
            if "cpu_usage" in health:
                olt.cpu_usage = health["cpu_usage"]
            if "memory_usage" in health:
                olt.memory_usage = health["memory_usage"]
            if "temperature" in health:
                olt.temperature = health["temperature"]
            if "uptime_seconds" in health:
                olt.uptime_seconds = health["uptime_seconds"]

        # Index existing ONUs by (pon_port, onu_id)
        existing_by_key = {
            (o.pon_port, o.onu_id): o
            for o in db.query(ONU).filter(ONU.olt_id == olt.id).all()
        }
        seen_keys = set()

        # Process ONUs
        for onu_data in olt_data.onus:
            key = (onu_data.pon_port, onu_data.onu_id)
            seen_keys.add(key)

            if key in existing_by_key:
                onu = existing_by_key[key]
                was_online = onu.is_online

                onu.mac_address = onu_data.mac_address
                onu.is_online = onu_data.is_online
                if onu_data.description:
                    onu.description = onu_data.description
                if onu_data.model:
                    onu.model = onu_data.model

                if onu_data.is_online:
                    if onu_data.distance is not None:
                        onu.distance = onu_data.distance
                    if onu_data.rx_power is not None:
                        onu.rx_power = onu_data.rx_power
                    if onu_data.onu_rx_power is not None:
                        onu.onu_rx_power = onu_data.onu_rx_power
                    if onu_data.onu_tx_power is not None:
                        onu.onu_tx_power = onu_data.onu_tx_power
                    if onu_data.onu_temperature is not None:
                        onu.onu_temperature = onu_data.onu_temperature
                    if onu_data.onu_voltage is not None:
                        onu.onu_voltage = onu_data.onu_voltage
                    if onu_data.onu_tx_bias is not None:
                        onu.onu_tx_bias = onu_data.onu_tx_bias
                    if onu_data.alive_time_seconds is not None:
                        onu.olt_alive_time = onu_data.alive_time_seconds
                    onu.last_seen = current_time
                    if onu.online_since is None:
                        onu.online_since = current_time

                # Status transitions
                if was_online and not onu_data.is_online:
                    onu.offline_reason = onu_data.offline_reason or "Unknown"
                    onu.olt_alive_time = None
                elif not was_online and onu_data.is_online:
                    onu.online_since = current_time
                    onu.offline_reason = None

                onu.updated_at = current_time
            else:
                # Create new ONU — respect the tenant's ONU plan limit.
                if _plan and _onu_count >= _plan.max_onus:
                    continue
                onu = ONU(
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                    olt_id=olt.id,
                    pon_port=onu_data.pon_port,
                    onu_id=onu_data.onu_id,
                    mac_address=onu_data.mac_address,
                    description=onu_data.description,
                    model=onu_data.model,
                    is_online=onu_data.is_online,
                    distance=onu_data.distance if onu_data.is_online else None,
                    rx_power=onu_data.rx_power if onu_data.is_online else None,
                    onu_rx_power=onu_data.onu_rx_power if onu_data.is_online else None,
                    onu_tx_power=onu_data.onu_tx_power if onu_data.is_online else None,
                    onu_temperature=onu_data.onu_temperature if onu_data.is_online else None,
                    onu_voltage=onu_data.onu_voltage if onu_data.is_online else None,
                    onu_tx_bias=onu_data.onu_tx_bias if onu_data.is_online else None,
                    online_since=current_time if onu_data.is_online else None,
                    last_seen=current_time if onu_data.is_online else None,
                    # An ONU can first appear via the agent already offline
                    # (e.g. discovered during a power outage); persist the
                    # reported reason instead of leaving it blank.
                    offline_reason=(onu_data.offline_reason or "Unknown") if not onu_data.is_online else None,
                )
                db.add(onu)
                db.flush()
                _onu_count += 1

            # Insert traffic history if there's traffic
            if onu_data.rx_kbps > 0 or onu_data.tx_kbps > 0:
                db.add(TrafficHistory(
                    tenant_id=tenant_id,
                    entity_type="onu",
                    entity_id=str(onu.id),
                    olt_id=olt.id,
                    pon_port=onu_data.pon_port,
                    onu_db_id=onu.id,
                    rx_kbps=onu_data.rx_kbps,
                    tx_kbps=onu_data.tx_kbps,
                    timestamp=current_time,
                ))

            onus_processed += 1

        # Mark ONUs not in payload as missing — but only if the agent
        # actually polled the OLT.  When agent can't reach it (0 ONUs),
        # skip this so SaaS-fallback-managed ONUs stay untouched.
        if not agent_unreachable:
            for key, onu in existing_by_key.items():
                if key not in seen_keys:
                    onu.missing_polls = (onu.missing_polls or 0) + 1
                    if onu.missing_polls >= 3 and onu.is_online:
                        onu.is_online = False
                        onu.offline_reason = "Agent: missing from poll"
                        onu.updated_at = current_time

        # Port traffic
        for pt in olt_data.port_traffic:
            if pt.rx_kbps > 0 or pt.tx_kbps > 0:
                db.add(PortTraffic(
                    tenant_id=tenant_id,
                    olt_id=olt.id,
                    port_type=pt.port_type,
                    port_number=pt.port_number,
                    rx_kbps=pt.rx_kbps,
                    tx_kbps=pt.tx_kbps,
                    timestamp=current_time,
                ))
                db.add(TrafficHistory(
                    tenant_id=tenant_id,
                    entity_type=pt.port_type,
                    entity_id=f"{olt.id}:{pt.port_type}:{pt.port_number}",
                    olt_id=olt.id,
                    pon_port=None,
                    onu_db_id=None,
                    rx_kbps=pt.rx_kbps,
                    tx_kbps=pt.tx_kbps,
                    timestamp=current_time,
                ))

        # PON aggregation + OLT total traffic history
        pon_agg: dict[int, dict[str, float]] = {}
        for onu_data in olt_data.onus:
            pon = onu_data.pon_port
            if pon not in pon_agg:
                pon_agg[pon] = {"rx_kbps": 0, "tx_kbps": 0}
            pon_agg[pon]["rx_kbps"] += onu_data.rx_kbps
            pon_agg[pon]["tx_kbps"] += onu_data.tx_kbps

        for pon, rates in pon_agg.items():
            if rates["rx_kbps"] > 0 or rates["tx_kbps"] > 0:
                db.add(TrafficHistory(
                    tenant_id=tenant_id,
                    entity_type="pon",
                    entity_id=f"{olt.id}:{pon}",
                    olt_id=olt.id,
                    pon_port=pon,
                    onu_db_id=None,
                    rx_kbps=rates["rx_kbps"],
                    tx_kbps=rates["tx_kbps"],
                    timestamp=current_time,
                ))

        total_rx = sum(o.rx_kbps for o in olt_data.onus)
        total_tx = sum(o.tx_kbps for o in olt_data.onus)
        if total_rx > 0 or total_tx > 0:
            db.add(TrafficHistory(
                tenant_id=tenant_id,
                entity_type="olt",
                entity_id=str(olt.id),
                olt_id=olt.id,
                pon_port=None,
                onu_db_id=None,
                rx_kbps=total_rx,
                tx_kbps=total_tx,
                timestamp=current_time,
            ))

    # Update agent key metadata
    agent_key.last_seen_at = current_time
    agent_key.last_seen_ip = request.client.host if request.client else None
    if payload.agent_version:
        agent_key.agent_version = payload.agent_version

    db.commit()

    return {"status": "ok", "onus_processed": onus_processed}


# ---------------------------------------------------------------------------
# Agent config endpoint — OLT auto-discovery
# ---------------------------------------------------------------------------


@router.get("/config")
def agent_config(
    request: Request,
    agent_key: AgentKey = Depends(require_agent_key),
    db: Session = Depends(_db),
):
    """Return the OLT list for this tenant so the agent auto-discovers devices.

    The agent calls this on startup and periodically. Credentials are decrypted
    server-side so the agent receives plaintext it can use directly.
    """
    from config import decrypt_sensitive

    tenant_id = agent_key.tenant_id
    workspace_id = agent_key.workspace_id

    olts = db.query(OLT).filter(
        OLT.tenant_id == tenant_id,
        OLT.workspace_id == workspace_id,
    ).all()

    olt_list = []
    for olt in olts:
        # Decrypt passwords
        try:
            password = decrypt_sensitive(olt.password) if olt.password else "admin"
        except Exception:
            password = "admin"
        try:
            web_password = decrypt_sensitive(olt.web_password) if olt.web_password else password
        except Exception:
            web_password = password

        olt_entry = {
            "name": olt.name,
            "ip_address": olt.ip_address,
            "model": olt.model or "",
            "snmp_community": getattr(olt, "snmp_community", None) or "public",
            "web_username": olt.web_username or olt.username or "admin",
            "web_password": web_password,
            "mikrotik": {
                "enabled": bool(getattr(olt, "mk_enabled", False)),
                "ip": getattr(olt, "mk_ip", None) or "",
                "username": getattr(olt, "mk_username", None) or "admin",
                "password": getattr(olt, "mk_password", None) or "",
                "port": getattr(olt, "mk_port", None) or 8728,
            },
        }
        olt_list.append(olt_entry)

    # Update last_seen
    agent_key.last_seen_at = datetime.utcnow()
    agent_key.last_seen_ip = request.client.host if request.client else None
    db.commit()

    return {
        "poll_interval": 30,
        "optical_every": 5,
        "olts": olt_list,
    }
