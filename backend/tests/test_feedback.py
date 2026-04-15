"""Feedback API tests (Phase 6)."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from config import generate_tenant_dek, wrap_tenant_dek  # noqa: E402
from feedback_routes import router as feedback_router  # noqa: E402
from models import (  # noqa: E402
    Base,
    Feedback,
    SessionLocal,
    Tenant,
    User,
    Workspace,
    engine,
    user_workspaces,
)
from tenancy import TenantContext, get_tenant_context  # noqa: E402

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


def _setup_tenant(staff: bool = False) -> tuple[Tenant, Workspace, User]:
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
            email=f"u-{os.urandom(2).hex()}@acme.com",
            password_hash="x",
            role="owner",
        )
        # is_staff lives in the user model only if Phase 6 added it; we
        # set it via setattr so the test still passes if the column doesn't
        # exist on this branch.
        if staff and hasattr(u, "is_staff"):
            u.is_staff = True
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


def _make_client(user: User) -> TestClient:
    app = FastAPI()
    app.include_router(feedback_router)

    def _override():
        db = SessionLocal()
        try:
            fresh = db.query(User).filter(User.id == user.id).first()
            return TenantContext(
                tenant_id=fresh.tenant_id,
                user=fresh,
                workspace_ids=[],
                role="owner",
            )
        finally:
            db.close()

    app.dependency_overrides[get_tenant_context] = _override
    return TestClient(app)


def test_submit_feedback_persists_row():
    _, _, user = _setup_tenant()
    client = _make_client(user)
    r = client.post(
        "/api/feedback",
        json={"category": "bug", "message": "polling stopped at 3am", "page_url": "/app/dashboard"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["category"] == "bug"
    assert body["message"] == "polling stopped at 3am"
    assert body["page_url"] == "/app/dashboard"

    db = SessionLocal()
    try:
        rows = db.query(Feedback).all()
        assert len(rows) == 1
        assert rows[0].user_id == user.id
        assert rows[0].tenant_id == user.tenant_id
    finally:
        db.close()


def test_submit_feedback_rejects_unknown_category():
    _, _, user = _setup_tenant()
    client = _make_client(user)
    r = client.post(
        "/api/feedback",
        json={"category": "rant", "message": "..."},
    )
    assert r.status_code == 400


def test_submit_feedback_rejects_short_message():
    _, _, user = _setup_tenant()
    client = _make_client(user)
    r = client.post(
        "/api/feedback",
        json={"category": "idea", "message": "x"},
    )
    assert r.status_code == 422  # Pydantic min_length


def test_list_my_feedback_only_returns_my_tenant():
    # Tenant A submits feedback, tenant B should never see it.
    _, _, user_a = _setup_tenant()
    _, _, user_b = _setup_tenant()

    client_a = _make_client(user_a)
    client_b = _make_client(user_b)

    client_a.post(
        "/api/feedback",
        json={"category": "praise", "message": "love it"},
    )

    a_list = client_a.get("/api/feedback").json()
    b_list = client_b.get("/api/feedback").json()
    assert len(a_list) == 1
    assert len(b_list) == 0


def test_admin_feedback_requires_staff_flag():
    _, _, user = _setup_tenant(staff=False)
    client = _make_client(user)
    r = client.get("/admin/feedback")
    # Without is_staff the route must refuse.
    assert r.status_code == 403
