"""WireGuard provisioning API (Phase 3.3).

Endpoints:
    POST /api/workspaces/{wid}/wireguard/provision
    GET  /api/workspaces/{wid}/wireguard/config
    GET  /api/workspaces/{wid}/wireguard/status
    PUT  /api/workspaces/{wid}/wireguard/lan-subnet   (Phase 3.5 onboarding)
    POST /api/workspaces/{wid}/wireguard/deprovision
    POST /api/workspaces/{wid}/wireguard/heartbeat   (called by install script)

All routes require `get_tenant_context` so a user can only ever provision
their own tenant's workspaces.
"""
from __future__ import annotations

import ipaddress
import logging
import subprocess
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import SessionLocal, Tenant, Workspace
from tenancy import TenantContext, get_tenant_context

from models import OLT

from .manager import (
    WG_INTERFACE,
    WG_KEEPALIVE,
    deprovision_workspace,
    provision_workspace,
    render_client_config,
    run_wg,
)

# In-memory rx counter cache, keyed by peer pubkey.
# Value: (rx_bytes, observed_at_epoch). Used by /status to detect when a
# customer tunnel goes silent: WG re-handshakes only every ~120s, but with
# persistent-keepalive=25s the rx counter should grow at least every 25s
# when the tunnel is alive. If rx hasn't grown for STALE_AFTER seconds, the
# peer is offline.
_rx_cache: dict[str, tuple[int, float]] = {}
STALE_AFTER = 30  # seconds


def _parse_wg_dump(output: str) -> dict[str, dict]:
    """Parse `wg show <iface> dump` into {pubkey: {handshake, rx, tx}}.

    Dump format (tab-separated, one peer per line after the first):
        <peer_pub>  <psk>  <endpoint>  <allowed>  <handshake>  <rx>  <tx>  <ka>
    """
    peers: dict[str, dict] = {}
    lines = output.strip().splitlines()
    for line in lines[1:]:  # skip interface header line
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        try:
            peers[parts[0]] = {
                "handshake": int(parts[4]),
                "rx": int(parts[5]),
                "tx": int(parts[6]),
            }
        except (ValueError, IndexError):
            continue
    return peers

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["wireguard"])


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _load_workspace(db: Session, ctx: TenantContext, wid: str) -> Workspace:
    ws = (
        db.query(Workspace)
        .filter(Workspace.id == wid, Workspace.tenant_id == ctx.tenant_id)
        .first()
    )
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


class ProvisionResponse(BaseModel):
    workspace_id: str
    cidr: str
    hub_address: str
    gateway_address: str
    public_key: str
    config: str
    status: str


@router.post("/{wid}/wireguard/provision", response_model=ProvisionResponse)
def provision(
    wid: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    """Allocate a /24, generate a keypair, add the peer to the hub.

    Returns a `wg-quick` config blob the customer can paste into their
    gateway. Idempotent — calling it twice on the same workspace returns
    the same config.
    """
    ws = _load_workspace(db, ctx, wid)
    tenant = db.query(Tenant).filter(Tenant.id == ctx.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    peer = provision_workspace(db, ws, tenant)
    return ProvisionResponse(
        workspace_id=peer.workspace_id,
        cidr=peer.cidr,
        hub_address=peer.hub_address,
        gateway_address=peer.gateway_address,
        public_key=peer.public_key,
        config=peer.config_blob,
        status=peer.status,
    )


@router.get("/{wid}/wireguard/config")
def get_config(
    wid: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    """Return the wg-quick config for an already-provisioned workspace.

    The private key has to be re-decrypted from the tenant DEK every time
    rather than stored in plaintext anywhere.
    """
    ws = _load_workspace(db, ctx, wid)
    if not ws.wg_subnet or not ws.wg_privkey_enc:
        raise HTTPException(status_code=409, detail="Workspace not provisioned yet")
    tenant = db.query(Tenant).filter(Tenant.id == ctx.tenant_id).first()
    from config import decrypt_for_tenant

    privkey = decrypt_for_tenant(tenant.dek_encrypted, ws.wg_privkey_enc)
    return {
        "cidr": ws.wg_subnet,
        "config": render_client_config(ws.wg_subnet, privkey),
        "status": ws.wg_status,
        "lan_subnet": ws.lan_subnet,
    }


@router.get("/{wid}/wireguard/status")
def get_status(
    wid: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    """Live status for a workspace's WG peer.

    Hits `wg show <iface> latest-handshakes` on every call so the dashboard
    reflects the true tunnel state without waiting for a background job.
    The query is fast (single syscall) and only returns this workspace's
    handshake from the parsed map, so it's safe to poll every few seconds.
    """
    ws = _load_workspace(db, ctx, wid)

    if ws.wg_pubkey:
        try:
            output = run_wg("show", WG_INTERFACE, "dump")
            peers = _parse_wg_dump(output)
            peer = peers.get(ws.wg_pubkey)
            now = time.time()

            if not peer or peer["handshake"] == 0:
                new_status = "pending"
            else:
                ws.last_handshake_at = datetime.utcfromtimestamp(peer["handshake"])
                rx = peer["rx"]
                cached = _rx_cache.get(ws.wg_pubkey)

                if cached is None:
                    # First observation. Seed the cache and trust the
                    # handshake — if the rx counter has any data and the
                    # handshake is recent (< 3min) the tunnel is alive.
                    _rx_cache[ws.wg_pubkey] = (rx, now)
                    age = now - peer["handshake"]
                    new_status = "connected" if age < 180 else "stale"
                else:
                    prev_rx, prev_t = cached
                    if rx > prev_rx:
                        # Counter advanced — keepalive landed, tunnel alive.
                        _rx_cache[ws.wg_pubkey] = (rx, now)
                        new_status = "connected"
                    elif now - prev_t >= STALE_AFTER:
                        # Counter has been frozen for too long. Mikrotik
                        # sends a keepalive every 25s, so 30s of silence
                        # means the peer is gone.
                        new_status = "stale"
                    else:
                        # Quiet but not yet long enough — keep prior state.
                        new_status = ws.wg_status or "connected"

            if ws.wg_status != new_status:
                ws.wg_status = new_status
            db.commit()
        except (RuntimeError, FileNotFoundError) as e:
            # `wg` not on this host (e.g. running in a non-hub container).
            # Fall back to whatever's stored in the DB.
            logger.debug(f"[wg] live status check skipped: {e}")

    return {
        "workspace_id": ws.id,
        "cidr": ws.wg_subnet,
        "status": ws.wg_status or "pending",
        "last_handshake_at": ws.last_handshake_at.isoformat()
        if ws.last_handshake_at
        else None,
    }


@router.post("/{wid}/wireguard/deprovision", status_code=status.HTTP_204_NO_CONTENT)
def deprovision(
    wid: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    ws = _load_workspace(db, ctx, wid)
    deprovision_workspace(db, ws)
    return None


class LanSubnetRequest(BaseModel):
    lan_subnet: str


class LanSubnetResponse(BaseModel):
    workspace_id: str
    lan_subnet: str
    routed: bool   # True if the cloud actually pushed routes to wg0


def _normalize_cidr(value: str) -> str:
    """Validate `value` and return its canonical network form.

    Rejects host bits set inside the network (e.g. 192.168.1.5/24 -> error).
    The customer should give us a network address; we don't silently mask
    out their typo because it's almost always a mistake worth surfacing.
    """
    try:
        net = ipaddress.ip_network(value.strip(), strict=True)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CIDR '{value}': {e}",
        )
    if net.version != 4:
        raise HTTPException(status_code=400, detail="Only IPv4 LAN subnets are supported")
    if net.prefixlen > 30:
        raise HTTPException(
            status_code=400,
            detail="LAN subnet prefix too small (need /30 or larger)",
        )
    return str(net)


def _push_lan_route(workspace: Workspace) -> bool:
    """Push the workspace's LAN subnet to wg0 + the kernel routing table.

    Returns True on success, False if `wg`/`ip` aren't on this host (e.g.
    we're running in a web worker that's not the hub). Failure is logged
    but never raises — the customer's config is saved either way and the
    next hub-side reconcile job will pick it up.
    """
    if not workspace.wg_pubkey or not workspace.wg_subnet or not workspace.lan_subnet:
        return False
    allowed = f"{workspace.wg_subnet},{workspace.lan_subnet}"
    try:
        run_wg(
            "set",
            WG_INTERFACE,
            "peer",
            workspace.wg_pubkey,
            "allowed-ips",
            allowed,
            "persistent-keepalive",
            str(WG_KEEPALIVE),
        )
    except (RuntimeError, FileNotFoundError) as e:
        logger.warning(f"[wg] lan-subnet allowed-ips push skipped: {e}")
        return False

    # Persist allowed-ips to /etc/wireguard/wg0.conf so the change
    # survives a hub reboot. The live `wg set` only updates the in-memory
    # interface; without `wg-quick save` the next `wg-quick down/up` cycle
    # would forget this peer's LAN routes. Note: `wg set wg0 save` is NOT
    # a valid command — only `wg-quick save <iface>` persists.
    try:
        subprocess.run(
            ["wg-quick", "save", WG_INTERFACE],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        stderr = getattr(e, "stderr", "") or ""
        logger.warning(f"[wg] wg-quick save skipped: {stderr.strip() or e}")
        # Non-fatal: in-memory state is correct, just won't survive reboot.

    # `wg set ... allowed-ips` updates cryptokey routing inside the WG
    # interface but does NOT touch the kernel routing table. Without an
    # `ip route` entry the cloud's polling worker has no way to send
    # packets at the LAN subnet through wg0. `ip route replace` is
    # idempotent — it adds the route or updates it if it already exists.
    try:
        subprocess.run(
            ["ip", "route", "replace", workspace.lan_subnet, "dev", WG_INTERFACE],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        stderr = getattr(e, "stderr", "") or ""
        logger.warning(f"[wg] ip route replace skipped: {stderr.strip() or e}")
        return False

    return True


def recalculate_workspace_routes(ws: Workspace, db: Session) -> bool:
    """Auto-derive WG routes from OLT IPs in the workspace.

    1. Query all OLTs in the workspace
    2. Compute each IP's /24, deduplicate
    3. Build allowed-ips = wg_subnet + all OLT /24s
    4. Run `wg set`, `ip route replace` per subnet, `wg-quick save`
    5. Save combined CIDRs to workspace.lan_subnet
    6. If no OLTs remain → reset to just wg_subnet, clear lan_subnet
    """
    if not ws.wg_pubkey or not ws.wg_subnet:
        logger.debug("[wg] recalculate skipped: workspace not provisioned")
        return False

    # Collect unique /24 subnets from all OLT IPs in this workspace
    olts = db.query(OLT).filter(OLT.workspace_id == ws.id).all()
    subnets: set[str] = set()
    for olt in olts:
        try:
            addr = ipaddress.ip_address(olt.ip_address.strip())
            net = ipaddress.ip_network(f"{addr}/24", strict=False)
            subnets.add(str(net))
        except ValueError:
            logger.warning("[wg] recalculate: bad OLT IP %s, skipping", olt.ip_address)
            continue

    # Build allowed-ips: always include the WG subnet itself
    allowed_parts = [ws.wg_subnet] + sorted(subnets)
    allowed = ",".join(allowed_parts)

    try:
        run_wg(
            "set", WG_INTERFACE, "peer", ws.wg_pubkey,
            "allowed-ips", allowed,
            "persistent-keepalive", str(WG_KEEPALIVE),
        )
    except (RuntimeError, FileNotFoundError) as e:
        logger.warning("[wg] recalculate allowed-ips push failed: %s", e)
        return False

    # Add kernel routes for each OLT subnet
    for subnet in subnets:
        try:
            subprocess.run(
                ["ip", "route", "replace", subnet, "dev", WG_INTERFACE],
                capture_output=True, text=True, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            stderr = getattr(e, "stderr", "") or ""
            logger.warning("[wg] ip route replace %s failed: %s", subnet, stderr.strip() or e)

    # Persist to wg0.conf
    try:
        subprocess.run(
            ["wg-quick", "save", WG_INTERFACE],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        stderr = getattr(e, "stderr", "") or ""
        logger.warning("[wg] wg-quick save skipped: %s", stderr.strip() or e)

    # Update workspace.lan_subnet
    if subnets:
        ws.lan_subnet = ",".join(sorted(subnets))
    else:
        ws.lan_subnet = None
    db.commit()

    logger.info(
        "[wg] recalculated routes for workspace %s: %d subnet(s) → %s",
        ws.id, len(subnets), ws.lan_subnet or "(none)",
    )
    return True


@router.put("/{wid}/wireguard/lan-subnet", response_model=LanSubnetResponse)
def set_lan_subnet(
    wid: str,
    payload: LanSubnetRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    """Declare which on-prem CIDR the customer's OLTs live on.

    The cloud-side hub uses this to:
      1. Add the LAN subnet to wg0's allowed-ips for this peer (so the
         kernel knows packets from this CIDR may arrive on the tunnel).
      2. Add a kernel route `ip route replace <lan> dev wg0` so packets
         the polling worker sends to OLT IPs go into the tunnel.

    Two customers cannot share the same LAN subnet — there is no way for
    the hub to disambiguate where to send packets when both peers claim
    192.168.1.0/24. We surface this as a 409 with a clear message.
    """
    ws = _load_workspace(db, ctx, wid)
    if not ws.wg_subnet or not ws.wg_pubkey:
        raise HTTPException(
            status_code=409,
            detail="Provision the WireGuard tunnel before setting a LAN subnet",
        )

    new_cidr = _normalize_cidr(payload.lan_subnet)
    new_net = ipaddress.ip_network(new_cidr)

    # Refuse a LAN that overlaps with the workspace's own /24 — that
    # would put two routes for the same destination in the kernel and
    # the polling worker's behavior would become non-deterministic.
    try:
        wg_net = ipaddress.ip_network(ws.wg_subnet)
        if new_net.overlaps(wg_net):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"LAN subnet {new_cidr} overlaps your WireGuard subnet "
                    f"{ws.wg_subnet}. Pick a different LAN range."
                ),
            )
    except ValueError:
        pass

    # Within-tenant overlap check — RLS already scopes this query to the
    # current tenant. Cross-tenant collisions (two customers picking the
    # same LAN) are a Phase 6 concern: the operator runs `SELECT cidr,
    # workspace_id FROM workspaces WHERE lan_subnet IS NOT NULL` to spot
    # them manually. With <50 tenants this is fine; the moment we have a
    # second beta user with overlapping LANs we'll add a SECURITY DEFINER
    # helper to bypass RLS for the global check. See plan §3.5 NAT
    # collision risk.
    others = (
        db.query(Workspace)
        .filter(Workspace.id != ws.id)
        .filter(Workspace.lan_subnet.isnot(None))
        .all()
    )
    for other in others:
        try:
            other_net = ipaddress.ip_network(other.lan_subnet)
        except ValueError:
            continue
        if new_net.overlaps(other_net):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"LAN subnet {new_cidr} overlaps workspace "
                    f"'{other.name}' ({other.lan_subnet}). Pick a different "
                    f"range, or NAT your OLTs into a unique subnet."
                ),
            )

    ws.lan_subnet = new_cidr
    db.commit()
    db.refresh(ws)

    routed = _push_lan_route(ws)
    return LanSubnetResponse(
        workspace_id=ws.id,
        lan_subnet=ws.lan_subnet,
        routed=routed,
    )


@router.post("/{wid}/wireguard/heartbeat")
def heartbeat(
    wid: str,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    """Called by the install script after a successful initial connect.

    Sets `wg_status='connected'` immediately so the dashboard reflects the
    install without waiting for the next handshake-poll cycle.
    """
    ws = _load_workspace(db, ctx, wid)
    first_connect = ws.wg_status != "connected"
    ws.wg_status = "connected"
    ws.last_handshake_at = datetime.utcnow()
    db.commit()

    # Phase 6 — only fire telemetry on the first successful connect, so the
    # event represents a true onboarding milestone rather than every poll.
    if first_connect:
        try:
            import telemetry
            telemetry.workspace_wg_connected(str(ctx.tenant_id), ws.id)
        except Exception:
            pass

    return {"status": "ok"}
