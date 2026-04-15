"""WireGuard manager tests (Phase 3.3, 3.6).

We monkey-patch `manager.run_wg` so the tests don't need a real `wg`
binary on the test runner. The contract being tested is purely:

    1. provisioning is idempotent
    2. keys + subnet are persisted on the workspace row
    3. the rendered wg-quick config contains the right fields
    4. handshake parsing rolls workspace status forward correctly
    5. deprovisioning frees the subnet and clears the keys
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["WG_SUPERNET"] = "10.99.0.0/22"
os.environ["WG_SUBNET_PREFIX"] = "24"
os.environ["WG_HUB_PUBKEY"] = "fakeHubPubKeyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
os.environ["WG_HUB_ENDPOINT"] = "wg.test.example.com:51820"

_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"

from config import generate_tenant_dek, wrap_tenant_dek  # noqa: E402
from models import Base, SessionLocal, Tenant, Workspace, engine  # noqa: E402
from wireguard import allocator, manager  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def reset_db():
    with engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            try:
                conn.execute(tbl.delete())
            except Exception:
                pass
    yield


@pytest.fixture(autouse=True)
def fake_wg(monkeypatch):
    """Replace manager.run_wg with a deterministic stub."""
    counter = {"n": 0}

    def stub(*args, input=None):
        if args == ("genkey",):
            counter["n"] += 1
            return f"PRIVKEY{counter['n']:03d}AAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n"
        if args[0] == "pubkey":
            return f"PUBKEY{counter['n']:03d}AAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n"
        if args[0] == "set":
            return ""
        if args[0:2] == ("show",) or args[0] == "show":
            return ""
        return ""

    monkeypatch.setattr(manager, "run_wg", stub)
    yield


def _make_tenant_workspace() -> tuple[Tenant, Workspace]:
    db = SessionLocal()
    try:
        t = Tenant(
            name="Acme",
            slug=f"acme-{os.urandom(3).hex()}",
            dek_encrypted=wrap_tenant_dek(generate_tenant_dek()),
        )
        db.add(t)
        db.flush()
        w = Workspace(tenant_id=t.id, name="HQ")
        db.add(w)
        db.commit()
        db.refresh(t)
        db.refresh(w)
        return t, w
    finally:
        db.close()


def test_provision_assigns_subnet_and_keys():
    tenant, ws = _make_tenant_workspace()
    db = SessionLocal()
    try:
        ws = db.merge(ws)
        tenant = db.merge(tenant)
        peer = manager.provision_workspace(db, ws, tenant)
        assert peer.cidr.startswith("10.99.")
        assert peer.cidr.endswith("/24")
        assert peer.public_key.startswith("PUBKEY")
        assert peer.private_key.startswith("PRIVKEY")
        assert "PrivateKey" in peer.config_blob
        assert peer.cidr in peer.config_blob
        assert "wg.test.example.com:51820" in peer.config_blob
    finally:
        db.close()


def test_provision_is_idempotent():
    tenant, ws = _make_tenant_workspace()
    db = SessionLocal()
    try:
        ws = db.merge(ws)
        tenant = db.merge(tenant)
        first = manager.provision_workspace(db, ws, tenant)
        second = manager.provision_workspace(db, ws, tenant)
        assert first.public_key == second.public_key
        assert first.cidr == second.cidr
        assert first.private_key == second.private_key
    finally:
        db.close()


def test_provision_persists_keys_under_tenant_dek():
    tenant, ws = _make_tenant_workspace()
    ws_id = ws.id
    tenant_dek = tenant.dek_encrypted
    db = SessionLocal()
    try:
        ws = db.merge(ws)
        tenant = db.merge(tenant)
        peer = manager.provision_workspace(db, ws, tenant)
    finally:
        db.close()

    db2 = SessionLocal()
    try:
        reloaded = db2.query(Workspace).filter(Workspace.id == ws_id).first()
        assert reloaded.wg_pubkey == peer.public_key
        assert reloaded.wg_privkey_enc.startswith("ENC:")

        from config import decrypt_for_tenant

        decrypted = decrypt_for_tenant(tenant_dek, reloaded.wg_privkey_enc)
        assert decrypted == peer.private_key
    finally:
        db2.close()


def test_deprovision_clears_keys_and_releases_subnet():
    tenant, ws = _make_tenant_workspace()
    db = SessionLocal()
    try:
        ws = db.merge(ws)
        tenant = db.merge(tenant)
        manager.provision_workspace(db, ws, tenant)
        assert allocator.get_workspace_subnet(db, ws.id) is not None

        manager.deprovision_workspace(db, ws)
        assert ws.wg_pubkey is None
        assert ws.wg_privkey_enc is None
        assert allocator.get_workspace_subnet(db, ws.id) is None
    finally:
        db.close()


def test_parse_handshakes_roundtrip():
    raw = (
        "PUBKEYa\t1700000000\n"
        "PUBKEYb\t1700000500\n"
        "PUBKEYc\t0\n"
    )
    parsed = manager.parse_handshakes(raw)
    assert parsed["PUBKEYa"] == 1700000000
    assert parsed["PUBKEYb"] == 1700000500
    assert parsed["PUBKEYc"] == 0


def test_update_handshakes_promotes_status(monkeypatch):
    tenant, ws = _make_tenant_workspace()
    db = SessionLocal()
    try:
        ws = db.merge(ws)
        tenant = db.merge(tenant)
        peer = manager.provision_workspace(db, ws, tenant)

        # Force the handshake epoch to "now" → should become "connected".
        now = int(time.time())

        def stub(*args, input=None):
            if args[0] == "show":
                return f"{peer.public_key}\t{now}\n"
            return ""

        monkeypatch.setattr(manager, "run_wg", stub)

        results = manager.update_handshakes(db)
        assert results[ws.id] == "connected"

        db.refresh(ws)
        assert ws.wg_status == "connected"
        assert ws.last_handshake_at is not None
    finally:
        db.close()


def test_update_handshakes_marks_stale_after_5min(monkeypatch):
    tenant, ws = _make_tenant_workspace()
    db = SessionLocal()
    try:
        ws = db.merge(ws)
        tenant = db.merge(tenant)
        peer = manager.provision_workspace(db, ws, tenant)

        ten_minutes_ago = int(time.time()) - 600

        def stub(*args, input=None):
            if args[0] == "show":
                return f"{peer.public_key}\t{ten_minutes_ago}\n"
            return ""

        monkeypatch.setattr(manager, "run_wg", stub)
        manager.update_handshakes(db)
        db.refresh(ws)
        assert ws.wg_status == "stale"
    finally:
        db.close()
