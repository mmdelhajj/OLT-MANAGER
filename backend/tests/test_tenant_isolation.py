"""Tests for tenant isolation at the application + ORM level.

These run against an in-memory SQLite database created by the conftest
fixture below. PostgreSQL Row-Level Security is verified by a separate
suite that requires a real Postgres instance (see
`tests/test_tenant_rls_postgres.py`, skipped on CI without DATABASE_URL).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Make backend/ importable.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Force a fresh in-memory SQLite engine BEFORE importing models, so the
# models module's `engine` global never points at the production DB.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import models  # noqa: E402  (after env setup)
from models import (  # noqa: E402
    OLT,
    Base,
    Tenant,
    User,
    Workspace,
    set_session_tenant,
)


@pytest.fixture()
def db():
    """Fresh in-memory SQLite DB with the Phase 1 schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _make_tenant(db, name: str, slug: str) -> Tenant:
    t = Tenant(name=name, slug=slug, plan="active", status="active")
    db.add(t)
    db.flush()
    return t


def _make_workspace(db, tenant: Tenant, name: str = "Default") -> Workspace:
    w = Workspace(tenant_id=tenant.id, name=name)
    db.add(w)
    db.flush()
    return w


def _make_olt(db, tenant: Tenant, workspace: Workspace, ip: str) -> OLT:
    olt = OLT(
        tenant_id=tenant.id,
        workspace_id=workspace.id,
        name=f"OLT {ip}",
        ip_address=ip,
        username="admin",
        password="ENC:fake",
    )
    db.add(olt)
    db.flush()
    return olt


def test_two_tenants_can_use_same_olt_ip(db):
    """The (tenant_id, ip_address) unique constraint must allow the same
    LAN IP in two different tenants — that's the whole point of per-tenant
    namespaces."""
    t1 = _make_tenant(db, "Acme", "acme")
    t2 = _make_tenant(db, "Globex", "globex")
    w1 = _make_workspace(db, t1)
    w2 = _make_workspace(db, t2)

    _make_olt(db, t1, w1, "192.168.1.10")
    _make_olt(db, t2, w2, "192.168.1.10")  # same IP, different tenant
    db.commit()

    assert db.query(OLT).count() == 2


def test_filter_by_tenant_id_isolates_rows(db):
    """At the ORM level (no RLS), explicit filtering must isolate tenants."""
    t1 = _make_tenant(db, "Acme", "acme")
    t2 = _make_tenant(db, "Globex", "globex")
    w1 = _make_workspace(db, t1)
    w2 = _make_workspace(db, t2)

    _make_olt(db, t1, w1, "10.0.0.1")
    _make_olt(db, t1, w1, "10.0.0.2")
    _make_olt(db, t2, w2, "10.0.0.1")
    db.commit()

    t1_olts = db.query(OLT).filter(OLT.tenant_id == t1.id).all()
    t2_olts = db.query(OLT).filter(OLT.tenant_id == t2.id).all()

    assert len(t1_olts) == 2
    assert len(t2_olts) == 1
    assert all(o.tenant_id == t1.id for o in t1_olts)
    assert all(o.tenant_id == t2.id for o in t2_olts)


def test_user_email_unique_within_tenant(db):
    """Two users in the same tenant can't share an email."""
    t = _make_tenant(db, "Acme", "acme")

    db.add(User(tenant_id=t.id, email="alice@acme.com", password_hash="x", role="owner"))
    db.commit()

    db.add(User(tenant_id=t.id, email="alice@acme.com", password_hash="y", role="operator"))
    with pytest.raises(Exception):
        db.commit()
    db.rollback()


def test_user_email_can_repeat_across_tenants(db):
    """The same email is allowed in different tenants."""
    t1 = _make_tenant(db, "Acme", "acme")
    t2 = _make_tenant(db, "Globex", "globex")

    db.add(User(tenant_id=t1.id, email="alice@example.com", password_hash="x", role="owner"))
    db.add(User(tenant_id=t2.id, email="alice@example.com", password_hash="y", role="owner"))
    db.commit()

    assert db.query(User).count() == 2


def test_set_session_tenant_writes_session_info(db):
    """The tenant tag lives in session.info so the after_begin event can
    pick it up. On SQLite the GUC SET is a no-op but the tag still works."""
    set_session_tenant(db, "tenant-a")
    assert db.info["tenant_id"] == "tenant-a"


def test_user_username_alias_still_works(db):
    """Backwards-compat shim: code that still references User.username
    should keep working until Phase 4 cleans it up."""
    t = _make_tenant(db, "Acme", "acme")
    u = User(tenant_id=t.id, email="bob@acme.com", password_hash="x", role="operator")
    assert u.username == "bob@acme.com"
    u.username = "robert@acme.com"
    assert u.email == "robert@acme.com"
