"""WireGuard hub provisioning + per-workspace peer lifecycle (Phase 3.3).

This module owns the SaaS-side WireGuard hub. It:

  * Generates a per-workspace keypair and stores the private key encrypted
    under the tenant's DEK.
  * Adds the new peer to the live `wg0` interface via `wg set`.
  * Persists peer config so a restart of the hub server can rebuild state.
  * Renders a `wg-quick` config blob for the customer to download.
  * Polls `wg show wg0 latest-handshakes` to update workspace status.

The actual `wg` and `wg-quick` system calls are wrapped behind small
helpers so unit tests can monkey-patch them out — `manager.run_wg(...)`
is the only place that shells out.

The module is conservative: every state-changing call is idempotent and
re-entry-safe so we can recover from a crash mid-provisioning.
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from config import decrypt_for_tenant, encrypt_for_tenant, unwrap_tenant_dek
from models import Tenant, Workspace

from .allocator import (
    SubnetExhaustedError,
    allocate_subnet,
    gateway_address,
    get_workspace_subnet,
    hub_address,
    release_subnet,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hub config (overridable via env so prod can move freely)
# ---------------------------------------------------------------------------

WG_INTERFACE = os.getenv("WG_INTERFACE", "wg0")
WG_HUB_ENDPOINT = os.getenv("WG_HUB_ENDPOINT", "wg.oltmanager.io:51820")
WG_HUB_PUBKEY = os.getenv("WG_HUB_PUBKEY", "")
WG_DNS = os.getenv("WG_DNS", "1.1.1.1")
# Persistent keepalive helps customer-side NAT routers keep the WG state
# table warm. 25s is the well-known sweet spot.
WG_KEEPALIVE = int(os.getenv("WG_KEEPALIVE", "25"))
WG_SUPERNET = os.getenv("WG_SUPERNET", "10.99.0.0/16")


@dataclass
class WireGuardPeer:
    """Live state of a workspace's WireGuard peer on the hub."""

    workspace_id: str
    cidr: str
    hub_address: str
    gateway_address: str
    public_key: str
    private_key: str  # decrypted for the lifetime of this object only
    config_blob: str  # ready-to-paste wg-quick config
    status: str  # pending|connected|stale


# ---------------------------------------------------------------------------
# Shell-out shims (mocked in tests)
# ---------------------------------------------------------------------------


def run_wg(*args: str, input: Optional[str] = None) -> str:
    """Run a `wg ...` command and return stdout. Raises on non-zero."""
    cmd = ["wg", *args]
    logger.debug(f"[wg] exec: {' '.join(cmd)}")
    proc = subprocess.run(
        cmd, input=input, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"wg {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    return proc.stdout


def generate_keypair() -> tuple[str, str]:
    """Return (private_key, public_key) base64 strings.

    Uses `wg genkey | wg pubkey`. We don't reimplement Curve25519 in Python
    because the system tool is the canonical source of truth for keys.
    """
    private = run_wg("genkey").strip()
    public = run_wg("pubkey", input=private + "\n").strip()
    return private, public


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


def provision_workspace(db: Session, workspace: Workspace, tenant: Tenant) -> WireGuardPeer:
    """Allocate subnet + keypair + add peer to hub. Idempotent.

    On re-entry (e.g. customer clicks "Provision" twice) we return the
    existing peer config without disturbing live state.
    """
    if not tenant.dek_encrypted:
        raise RuntimeError(
            f"Tenant {tenant.id} has no DEK — provisioning blocked"
        )

    cidr = workspace.wg_subnet or get_workspace_subnet(db, workspace.id)
    if not cidr:
        cidr = allocate_subnet(db, workspace.id)
        workspace.wg_subnet = cidr

    if workspace.wg_pubkey and workspace.wg_privkey_enc:
        # Already provisioned — recover state.
        privkey = decrypt_for_tenant(tenant.dek_encrypted, workspace.wg_privkey_enc)
        pubkey = workspace.wg_pubkey
    else:
        privkey, pubkey = generate_keypair()
        workspace.wg_pubkey = pubkey
        workspace.wg_privkey_enc = encrypt_for_tenant(tenant.dek_encrypted, privkey)
        workspace.wg_status = "pending"
        db.flush()

    # Add the peer to the live hub interface. The hub side stores the
    # *customer's* public key (we generated it on the customer's behalf
    # in this MVP — see install script). For the long-term plan the
    # customer will generate their own private key, paste their pubkey
    # into the dashboard, and the hub will only ever see the public key.
    try:
        run_wg(
            "set",
            WG_INTERFACE,
            "peer",
            pubkey,
            "allowed-ips",
            cidr,
            "persistent-keepalive",
            str(WG_KEEPALIVE),
        )
    except (RuntimeError, FileNotFoundError) as e:
        # Don't fail provisioning just because the hub binary isn't on
        # this machine — dashboard provisioning is also called from web
        # workers that don't have wg installed. The dedicated hub-sync
        # job (run_hub_sync) reconciles all peers periodically.
        logger.warning(f"[wg] live peer add skipped on this host: {e}")
    else:
        # Persist to /etc/wireguard/wg0.conf via wg-quick save so the
        # peer survives a hub reboot. `wg set wg0 save` is NOT a valid
        # subcommand — only wg-quick can persist. Failure here is
        # non-fatal: in-memory state is right, but a reboot would lose
        # the peer until the customer re-provisions.
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

    db.commit()

    return WireGuardPeer(
        workspace_id=workspace.id,
        cidr=cidr,
        hub_address=hub_address(cidr),
        gateway_address=gateway_address(cidr),
        public_key=pubkey,
        private_key=privkey,
        config_blob=render_client_config(cidr, privkey),
        status=workspace.wg_status or "pending",
    )


def deprovision_workspace(db: Session, workspace: Workspace) -> None:
    """Tear down a workspace's WG peer. Idempotent.

    Removes the peer from the hub, releases the subnet, and zeroes out
    the workspace's stored keys. Used on workspace delete and on tenant
    hard-delete.
    """
    if workspace.wg_pubkey:
        try:
            run_wg("set", WG_INTERFACE, "peer", workspace.wg_pubkey, "remove")
        except (RuntimeError, FileNotFoundError) as e:
            logger.warning(f"[wg] live peer remove skipped: {e}")
        else:
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

    workspace.wg_pubkey = None
    workspace.wg_privkey_enc = None
    workspace.wg_status = "pending"
    workspace.last_handshake_at = None
    release_subnet(db, workspace.id)
    db.commit()


def render_client_config(cidr: str, private_key: str) -> str:
    """Render a `wg-quick` config that the customer can drop into /etc/wireguard."""
    return (
        "[Interface]\n"
        f"PrivateKey = {private_key}\n"
        f"Address = {gateway_address(cidr)}/32\n"
        f"DNS = {WG_DNS}\n"
        "\n"
        "[Peer]\n"
        f"PublicKey = {WG_HUB_PUBKEY}\n"
        f"Endpoint = {WG_HUB_ENDPOINT}\n"
        f"AllowedIPs = {cidr}\n"
        f"PersistentKeepalive = {WG_KEEPALIVE}\n"
    )


def render_mikrotik_script(
    cidr: str,
    private_key: str,
    workspace_name: str = "Default",
    tenant_name: str = "",
) -> str:
    """Render a single-paste RouterOS 7.x script that sets up the OLT
    Manager WireGuard tunnel.  Self-cleaning: removes any previous
    oltmanager config first so re-pasting is safe.
    """
    import ipaddress as _ip
    endpoint_host, _, endpoint_port = WG_HUB_ENDPOINT.partition(":")
    endpoint_port = endpoint_port or "51820"
    gw_addr = gateway_address(cidr)
    # Server's real WG IP — first host in the supernet (10.99.0.1)
    server_ip = str(next(_ip.ip_network(WG_SUPERNET).hosts()))
    # Single block — paste into Mikrotik terminal as-is.
    return (
        '{put "\\n\\n\\r================================\\r\\n'
        '   OLT Manager Connection Script\\r\\n'
        '================================\\n"; '
        '/interface wireguard peers remove [find where interface="oltmanager"]; '
        '/interface wireguard remove [find where name="oltmanager"]; '
        '/ip firewall filter remove [find where comment~"OLT Manager"]; '
        '/ip firewall nat remove [find where comment~"OLT Manager"]; '
        '/ip route remove [find where comment~"OLT Manager"]; '
        '/ip address remove [find where interface="oltmanager"]; '
        'put "Cleaning old config... Done!"; '
        f'/interface wireguard add name=oltmanager mtu=1420 listen-port=0 private-key="{private_key}"; '
        'put "Creating VPN interface... Done!"; '
        f'/interface/wireguard/peers/add interface=oltmanager '
        f'public-key="{WG_HUB_PUBKEY}" '
        f"endpoint-address={endpoint_host} "
        f"endpoint-port={endpoint_port} "
        # Scope to THIS workspace's own subnet + the hub only — never the whole
        # supernet, or one tenant's router could cryptokey-route to another
        # tenant's /24 (cross-tenant reachability).
        f"allowed-address={cidr},{server_ip}/32 "
        "persistent-keepalive=25; "
        'put "Adding server peer... Done!"; '
        f"/ip address add address={gw_addr}/24 interface=oltmanager; "
        f'/ip route add dst-address={server_ip}/32 gateway=oltmanager comment="OLT Manager - route"; '
        'put "Assigning VPN IP... Done!"; '
        '/ip firewall filter add chain=input in-interface=oltmanager '
        'action=accept place-before=*0 comment="OLT Manager - input"; '
        '/ip firewall filter add chain=forward in-interface=oltmanager '
        'action=accept place-before=*0 comment="OLT Manager - forward"; '
        'put "Adding firewall rules... Done!"; '
        f'/ip firewall nat add chain=srcnat src-address={server_ip}/32 '
        'action=masquerade comment="OLT Manager - NAT"; '
        'put "Adding NAT masquerade... Done!"; '
        f'put "\\r\\nSUCCESS!! Your router is connected to OLT Manager!\\r\\n'
        f"VPN IP: {gw_addr}\\r\\n"
        f"Verify: /ping {server_ip}\\r\\n"
        '"; }'
    )


# ---------------------------------------------------------------------------
# Health monitoring (Phase 3.6)
# ---------------------------------------------------------------------------


def parse_handshakes(output: str) -> dict[str, int]:
    """Parse `wg show <if> latest-handshakes` into {pubkey: epoch_seconds}."""
    out: dict[str, int] = {}
    for line in output.strip().splitlines():
        parts = line.split()
        if len(parts) >= 2:
            try:
                out[parts[0]] = int(parts[1])
            except ValueError:
                continue
    return out


def update_handshakes(db: Session) -> dict[str, str]:
    """Refresh `wg_status` + `last_handshake_at` for every workspace.

    Returns a {workspace_id: status} dict for logging/metrics.
    """
    try:
        output = run_wg("show", WG_INTERFACE, "latest-handshakes")
    except (RuntimeError, FileNotFoundError) as e:
        logger.warning(f"[wg] handshake poll skipped: {e}")
        return {}

    handshakes = parse_handshakes(output)
    # Use time.time() (true UTC epoch) — datetime.utcnow().timestamp() is
    # wrong on non-UTC hosts because .timestamp() interprets naive datetimes
    # as LOCAL time. This bug ate an hour of debugging in Phase 3 — don't
    # reintroduce it.
    now = time.time()
    results: dict[str, str] = {}

    for workspace in db.query(Workspace).filter(Workspace.wg_pubkey.isnot(None)):
        ts = handshakes.get(workspace.wg_pubkey, 0)
        if ts == 0:
            new_status = "pending"
        else:
            workspace.last_handshake_at = datetime.utcfromtimestamp(ts)
            age = now - ts
            new_status = "connected" if age < 300 else "stale"

        if workspace.wg_status != new_status:
            logger.info(
                f"[wg] workspace {workspace.id}: {workspace.wg_status} -> {new_status}"
            )
            workspace.wg_status = new_status
        results[workspace.id] = new_status

    db.commit()
    return results
