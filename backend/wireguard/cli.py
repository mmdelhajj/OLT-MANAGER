"""Operator CLI for the WireGuard hub.

Usage:
    python -m wireguard.cli reconcile-hub
        Re-adds every workspace peer to the live `wg0` interface from the
        database. Idempotent. Used after a hub host rebuild.

    python -m wireguard.cli list-peers
        Print every workspace's CIDR + pubkey + last_handshake_at.

    python -m wireguard.cli poll-handshakes
        One-shot handshake poll (the background job runs this every 60s).
"""
from __future__ import annotations

import argparse
import logging
import sys

from models import SessionLocal, Workspace

from . import manager

logger = logging.getLogger(__name__)


def reconcile_hub() -> int:
    db = SessionLocal()
    count = 0
    try:
        for ws in db.query(Workspace).filter(Workspace.wg_pubkey.isnot(None)):
            try:
                manager.run_wg(
                    "set",
                    manager.WG_INTERFACE,
                    "peer",
                    ws.wg_pubkey,
                    "allowed-ips",
                    ws.wg_subnet,
                    "persistent-keepalive",
                    str(manager.WG_KEEPALIVE),
                )
                count += 1
            except (RuntimeError, FileNotFoundError) as e:
                logger.error(f"[wg] reconcile failed for {ws.id}: {e}")

        try:
            manager.run_wg("set", manager.WG_INTERFACE, "save")
        except (RuntimeError, FileNotFoundError):
            pass
    finally:
        db.close()

    print(f"Reconciled {count} peers on {manager.WG_INTERFACE}")
    return 0


def list_peers() -> int:
    db = SessionLocal()
    try:
        rows = (
            db.query(Workspace)
            .filter(Workspace.wg_pubkey.isnot(None))
            .order_by(Workspace.created_at)
            .all()
        )
        for ws in rows:
            print(
                f"{ws.id}\t{ws.wg_subnet}\t{ws.wg_status}\t"
                f"{ws.last_handshake_at or '-'}\t{ws.wg_pubkey}"
            )
    finally:
        db.close()
    return 0


def poll_handshakes() -> int:
    db = SessionLocal()
    try:
        results = manager.update_handshakes(db)
        for wid, status in results.items():
            print(f"{wid}\t{status}")
    finally:
        db.close()
    return 0


COMMANDS = {
    "reconcile-hub": reconcile_hub,
    "list-peers": list_peers,
    "poll-handshakes": poll_handshakes,
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="wireguard.cli")
    parser.add_argument("command", choices=list(COMMANDS.keys()))
    args = parser.parse_args(argv)
    return COMMANDS[args.command]()


if __name__ == "__main__":
    sys.exit(main())
