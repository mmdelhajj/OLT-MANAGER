"""Wireguard provisioning HTTP route tests (Phase 3.3)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ["WG_SUPERNET"] = "10.99.0.0/22"
os.environ["WG_HUB_PUBKEY"] = "fakeHub" + "A" * 36 + "="
os.environ["WG_HUB_ENDPOINT"] = "wg.test.example:51820"

_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from config import generate_tenant_dek, wrap_tenant_dek  # noqa: E402
from models import (  # noqa: E402
    Base,
    SessionLocal,
    Tenant,
    User,
    Workspace,
    engine,
    user_workspaces,
)
from tenancy import TenantContext, get_tenant_context  # noqa: E402
from wireguard import manager  # noqa: E402
from wireguard.routes import router as wg_router  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def reset():
    with engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            try:
                conn.execute(tbl.delete())
            except Exception:
                pass
    yield


@pytest.fixture(autouse=True)
def fake_wg(monkeypatch):
    counter = {"n": 0}

    def stub(*args, input=None):
        if args == ("genkey",):
            counter["n"] += 1
            return f"PRIVKEY{counter['n']:03d}AAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n"
        if args[0] == "pubkey":
            return f"PUBKEY{counter['n']:03d}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=\n"
        return ""

    monkeypatch.setattr(manager, "run_wg", stub)
    yield


def _setup_tenant() -> tuple[Tenant, Workspace, User]:
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
        db.flush()
        u = User(
            tenant_id=t.id,
            email=f"owner-{os.urandom(2).hex()}@acme.com",
            password_hash="x",
            role="owner",
        )
        db.add(u)
        db.flush()
        db.execute(
            user_workspaces.insert().values(
                user_id=u.id, workspace_id=w.id, role="admin"
            )
        )
        db.commit()
        db.refresh(t)
        db.refresh(w)
        db.refresh(u)
        return t, w, u
    finally:
        db.close()


def _make_client(user: User, workspace: Workspace) -> TestClient:
    app = FastAPI()
    app.include_router(wg_router)

    def _override():
        # Re-fetch the user inside the override so the returned object is
        # bound to a fresh session — otherwise we'd hand a detached row
        # to the route and any lazy attribute access would explode.
        db = SessionLocal()
        try:
            fresh = db.query(User).filter(User.id == user.id).first()
            return TenantContext(
                tenant_id=fresh.tenant_id,
                user=fresh,
                workspace_ids=[workspace.id],
                role="owner",
            )
        finally:
            db.close()

    app.dependency_overrides[get_tenant_context] = _override
    return TestClient(app)


def test_provision_returns_config_blob():
    tenant, ws, user = _setup_tenant()
    client = _make_client(user, ws)
    r = client.post(f"/api/workspaces/{ws.id}/wireguard/provision")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["cidr"].startswith("10.99.")
    assert "PrivateKey" in body["config"]
    assert body["public_key"].startswith("PUBKEY")
    assert body["status"] in ("pending", "connected")


def test_provision_is_idempotent_via_http():
    tenant, ws, user = _setup_tenant()
    client = _make_client(user, ws)
    r1 = client.post(f"/api/workspaces/{ws.id}/wireguard/provision").json()
    r2 = client.post(f"/api/workspaces/{ws.id}/wireguard/provision").json()
    assert r1["public_key"] == r2["public_key"]
    assert r1["cidr"] == r2["cidr"]


def test_get_config_after_provision():
    tenant, ws, user = _setup_tenant()
    client = _make_client(user, ws)
    client.post(f"/api/workspaces/{ws.id}/wireguard/provision")
    r = client.get(f"/api/workspaces/{ws.id}/wireguard/config")
    assert r.status_code == 200
    assert "PrivateKey" in r.json()["config"]


def test_get_config_before_provision_returns_409():
    tenant, ws, user = _setup_tenant()
    client = _make_client(user, ws)
    r = client.get(f"/api/workspaces/{ws.id}/wireguard/config")
    assert r.status_code == 409


def test_status_endpoint_reports_pending_initially():
    tenant, ws, user = _setup_tenant()
    client = _make_client(user, ws)
    r = client.get(f"/api/workspaces/{ws.id}/wireguard/status")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_heartbeat_marks_connected():
    tenant, ws, user = _setup_tenant()
    client = _make_client(user, ws)
    client.post(f"/api/workspaces/{ws.id}/wireguard/provision")
    r = client.post(f"/api/workspaces/{ws.id}/wireguard/heartbeat")
    assert r.status_code == 200

    s = client.get(f"/api/workspaces/{ws.id}/wireguard/status").json()
    assert s["status"] == "connected"
    assert s["last_handshake_at"] is not None


def test_deprovision_returns_204_and_clears_state():
    tenant, ws, user = _setup_tenant()
    client = _make_client(user, ws)
    client.post(f"/api/workspaces/{ws.id}/wireguard/provision")
    r = client.post(f"/api/workspaces/{ws.id}/wireguard/deprovision")
    assert r.status_code == 204

    # After deprovision the config endpoint goes back to 409.
    assert client.get(f"/api/workspaces/{ws.id}/wireguard/config").status_code == 409


def test_cross_tenant_access_returns_404():
    """Workspace IDs are tenant-scoped — another tenant must get 404, not data."""
    _, ws_a, user_a = _setup_tenant()
    _, ws_b, _user_b = _setup_tenant()
    client = _make_client(user_a, ws_a)
    # user_a tries to provision tenant B's workspace
    r = client.post(f"/api/workspaces/{ws_b.id}/wireguard/provision")
    assert r.status_code == 404
