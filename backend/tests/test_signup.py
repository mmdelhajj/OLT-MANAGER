"""Signup flow tests (Phase 2.2).

Uses an in-memory SQLite DB and FastAPI's TestClient to drive
/auth/register, /auth/login, /auth/forgot-password, /auth/reset-password,
/auth/verify-email end-to-end without any external services.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Use a file-backed SQLite so the same DB is shared between the test
# session factory and the routes' SessionLocal (in-memory has separate
# connections per Session by default).
import tempfile
_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from auth_routes import router as auth_router, _verify_tokens, _reset_tokens  # noqa: E402
from models import Base, SessionLocal, User, engine  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(auth_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def clean_db():
    # Wipe between tests so unique-email assertions don't bleed.
    with engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            try:
                conn.execute(tbl.delete())
            except Exception:
                pass
    _verify_tokens.clear()
    _reset_tokens.clear()
    yield


def test_register_creates_tenant_and_owner(client):
    r = client.post("/auth/register", json={
        "email": "alice@acme.com",
        "password": "Sup3rSecret!",
        "company_name": "Acme Telecom",
        "full_name": "Alice",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["role"] == "owner"
    assert body["tenant_id"]
    assert body["access_token"]


def test_register_rejects_weak_password(client):
    r = client.post("/auth/register", json={
        "email": "bob@acme.com",
        "password": "short",
        "company_name": "Acme",
    })
    assert r.status_code == 400


def test_register_rejects_duplicate_email(client):
    body = {"email": "carol@acme.com", "password": "Sup3rSecret!", "company_name": "Acme"}
    assert client.post("/auth/register", json=body).status_code == 201
    r2 = client.post("/auth/register", json=body)
    assert r2.status_code == 409


def test_login_returns_jwt_after_register(client):
    client.post("/auth/register", json={
        "email": "dave@acme.com",
        "password": "Sup3rSecret!",
        "company_name": "Acme",
    })
    r = client.post("/auth/login", json={
        "email": "dave@acme.com",
        "password": "Sup3rSecret!",
    })
    assert r.status_code == 200, r.text
    assert r.json()["access_token"]


def test_login_rejects_wrong_password(client):
    client.post("/auth/register", json={
        "email": "eve@acme.com",
        "password": "Sup3rSecret!",
        "company_name": "Acme",
    })
    r = client.post("/auth/login", json={"email": "eve@acme.com", "password": "wrong"})
    assert r.status_code == 401


def test_forgot_password_always_202(client):
    """Anti-enumeration: same response whether the email exists or not."""
    r1 = client.post("/auth/forgot-password", json={"email": "ghost@nowhere.io"})
    assert r1.status_code == 202
    client.post("/auth/register", json={
        "email": "frank@acme.com",
        "password": "Sup3rSecret!",
        "company_name": "Acme",
    })
    r2 = client.post("/auth/forgot-password", json={"email": "frank@acme.com"})
    assert r2.status_code == 202


def test_reset_password_consumes_token(client):
    client.post("/auth/register", json={
        "email": "grace@acme.com",
        "password": "Sup3rSecret!",
        "company_name": "Acme",
    })
    client.post("/auth/forgot-password", json={"email": "grace@acme.com"})
    # Pluck the issued token from the in-memory store.
    assert len(_reset_tokens) == 1
    token = next(iter(_reset_tokens.keys()))

    r = client.post("/auth/reset-password", json={
        "token": token,
        "password": "NewSecret123!",
    })
    assert r.status_code == 200

    # Old password fails, new password works.
    assert client.post("/auth/login", json={
        "email": "grace@acme.com",
        "password": "Sup3rSecret!",
    }).status_code == 401
    assert client.post("/auth/login", json={
        "email": "grace@acme.com",
        "password": "NewSecret123!",
    }).status_code == 200


def test_verify_email_marks_verified(client):
    client.post("/auth/register", json={
        "email": "henry@acme.com",
        "password": "Sup3rSecret!",
        "company_name": "Acme",
    })
    assert len(_verify_tokens) == 1
    token = next(iter(_verify_tokens.keys()))

    r = client.post("/auth/verify-email", json={"token": token})
    assert r.status_code == 200
    assert r.json()["status"] == "verified"

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == "henry@acme.com").first()
        assert u.email_verified_at is not None
    finally:
        db.close()


def test_invalid_reset_token_rejected(client):
    r = client.post("/auth/reset-password", json={"token": "garbage", "password": "Sup3rSecret!"})
    assert r.status_code == 400
