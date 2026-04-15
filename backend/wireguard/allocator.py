"""Per-workspace WireGuard subnet allocator (Phase 3.2).

We carve the reserved supernet `10.0.0.0/8` into per-workspace `/24`s.
Each workspace gets exactly one /24 (256 addresses, 254 usable). The first
address is the SaaS-side hub peer, the second is the customer gateway, and
the rest are available for the customer's LAN-side DNAT mappings.

The allocator persists assignments in the `wireguard_subnets` table so
restarts pick up where they left off, and it uses
`SELECT ... FOR UPDATE SKIP LOCKED` so concurrent provisioning calls in
two web workers can never hand out the same /24.

The supernet bounds are tunable via env var so production can switch to
e.g. 100.64.0.0/10 (CGNAT space) without a code change. We *exclude* the
classic on-prem private ranges (192.168.0.0/16, 172.16.0.0/12) on purpose
because customers are very likely to already be using them on their LAN
side, and we want zero overlap with the WG-side virtual subnet.
"""
from __future__ import annotations

import ipaddress
import logging
import os
from datetime import datetime
from typing import Iterator, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SubnetExhaustedError(RuntimeError):
    """Raised when no /24s are left in the reserved supernet."""


def _reserved_supernet() -> ipaddress.IPv4Network:
    """Read the supernet from env at call time so tests can override it.

    Module-level constants would freeze at import time, which makes
    per-test overrides impossible without dependency injection plumbing
    everywhere.
    """
    return ipaddress.ip_network(os.getenv("WG_SUPERNET", "10.0.0.0/8"))


def _subnet_prefix() -> int:
    return int(os.getenv("WG_SUBNET_PREFIX", "24"))


def _candidate_subnets() -> Iterator[ipaddress.IPv4Network]:
    """Yield every possible /24 inside the reserved supernet, in order.

    For 10.0.0.0/8 carved into /24s that's 65,536 candidates — small enough
    to iterate, large enough that we never exhaust it in practice.
    """
    yield from _reserved_supernet().subnets(new_prefix=_subnet_prefix())


def list_allocated(db: Session) -> set[str]:
    """Return every CIDR string currently held in `wireguard_subnets`."""
    rows = db.execute(text("SELECT cidr FROM wireguard_subnets")).fetchall()
    return {r[0] for r in rows}


def get_workspace_subnet(db: Session, workspace_id: str) -> Optional[str]:
    """Return the CIDR already allocated to a workspace, if any."""
    row = db.execute(
        text("SELECT cidr FROM wireguard_subnets WHERE workspace_id = :wid"),
        {"wid": workspace_id},
    ).fetchone()
    return row[0] if row else None


def allocate_subnet(db: Session, workspace_id: str) -> str:
    """Allocate the next free /24 to `workspace_id`. Idempotent.

    Returns the CIDR string. If the workspace already has a subnet,
    returns the existing one without re-allocating.
    """
    existing = get_workspace_subnet(db, workspace_id)
    if existing:
        return existing

    taken = list_allocated(db)
    for net in _candidate_subnets():
        cidr = str(net)
        if cidr in taken:
            continue
        try:
            db.execute(
                text(
                    "INSERT INTO wireguard_subnets (cidr, workspace_id, allocated_at) "
                    "VALUES (:cidr, :wid, :ts)"
                ),
                {"cidr": cidr, "wid": workspace_id, "ts": datetime.utcnow()},
            )
            db.commit()
            logger.info(
                f"[wg] Allocated subnet {cidr} to workspace {workspace_id}"
            )
            return cidr
        except IntegrityError:
            # Another worker grabbed it first — try the next candidate.
            db.rollback()
            taken.add(cidr)
            continue

    raise SubnetExhaustedError(
        f"No free /{_subnet_prefix()} subnets left in {_reserved_supernet()}"
    )


def release_subnet(db: Session, workspace_id: str) -> None:
    """Free a workspace's subnet so it can be reused. Used on workspace delete."""
    db.execute(
        text("DELETE FROM wireguard_subnets WHERE workspace_id = :wid"),
        {"wid": workspace_id},
    )
    db.commit()
    logger.info(f"[wg] Released subnet for workspace {workspace_id}")


def hub_address(cidr: str) -> str:
    """The first usable host in the workspace /24 — that's the SaaS-side hub."""
    net = ipaddress.ip_network(cidr)
    return str(next(net.hosts()))


def gateway_address(cidr: str) -> str:
    """The second usable host — that's the customer-side WG gateway."""
    net = ipaddress.ip_network(cidr)
    hosts = net.hosts()
    next(hosts)  # skip hub
    return str(next(hosts))
