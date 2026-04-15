"""PostgreSQL Row-Level Security smoke tests.

Skipped unless DATABASE_URL points at a real Postgres instance — these
verify the actual RLS policies installed by migration 0004.

Run locally with::

    DATABASE_URL=postgresql://localhost/oltmanager_test \\
        alembic upgrade head && \\
        pytest tests/test_tenant_rls_postgres.py
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DB_URL = os.getenv("DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    not DB_URL.startswith(("postgresql://", "postgres://", "postgresql+")),
    reason="RLS test requires a Postgres DATABASE_URL",
)


@pytest.fixture(scope="module")
def engine():
    from sqlalchemy import create_engine
    eng = create_engine(DB_URL, future=True)
    yield eng
    eng.dispose()


@pytest.fixture()
def two_tenants(engine):
    """Insert two tenants + one OLT each, return their IDs."""
    from sqlalchemy import text

    t1 = str(uuid.uuid4())
    t2 = str(uuid.uuid4())
    w1 = str(uuid.uuid4())
    w2 = str(uuid.uuid4())

    with engine.begin() as conn:
        # Bypass RLS for setup by clearing the GUC.
        conn.execute(text("SET LOCAL app.current_tenant_id TO ''"))
        for tid, slug in [(t1, "rls-a"), (t2, "rls-b")]:
            conn.execute(
                text(
                    "INSERT INTO tenants (id, name, slug, plan, status) "
                    "VALUES (:id, :name, :slug, 'active', 'active')"
                ),
                {"id": tid, "name": slug, "slug": slug},
            )
        for wid, tid in [(w1, t1), (w2, t2)]:
            conn.execute(
                text(
                    "INSERT INTO workspaces (id, tenant_id, name) "
                    "VALUES (:id, :tid, 'Default')"
                ),
                {"id": wid, "tid": tid},
            )
        for wid, tid, ip in [(w1, t1, "10.0.0.1"), (w2, t2, "10.0.0.1")]:
            conn.execute(
                text(
                    "INSERT INTO olts "
                    "(tenant_id, workspace_id, name, ip_address, username, password) "
                    "VALUES (:tid, :wid, 'olt', :ip, 'admin', 'ENC:x')"
                ),
                {"tid": tid, "wid": wid, "ip": ip},
            )

    yield t1, t2

    with engine.begin() as conn:
        conn.execute(text("SET LOCAL app.current_tenant_id TO ''"))
        for tid in (t1, t2):
            conn.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tid})


def test_session_scoped_to_tenant_a_sees_only_tenant_a(engine, two_tenants):
    """With the GUC set to tenant A's id, SELECT from olts must return
    exactly the rows belonging to A."""
    from sqlalchemy import text

    t1, t2 = two_tenants

    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL app.current_tenant_id TO '{t1}'"))
        rows = conn.execute(text("SELECT tenant_id FROM olts")).fetchall()
        assert all(r[0] == t1 for r in rows)
        assert len(rows) >= 1

    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL app.current_tenant_id TO '{t2}'"))
        rows = conn.execute(text("SELECT tenant_id FROM olts")).fetchall()
        assert all(r[0] == t2 for r in rows)


def test_no_tenant_set_returns_zero_rows(engine, two_tenants):
    """Fail-closed: if the GUC is unset, RLS denies all rows."""
    from sqlalchemy import text

    with engine.begin() as conn:
        # current_setting('app.current_tenant_id', true) returns NULL,
        # which never matches tenant_id, so policy returns nothing.
        conn.execute(text("RESET app.current_tenant_id"))
        rows = conn.execute(text("SELECT * FROM olts")).fetchall()
        assert rows == []


def test_cross_tenant_delete_blocked(engine, two_tenants):
    """A DELETE issued under tenant A's GUC must NOT touch tenant B's rows."""
    from sqlalchemy import text

    t1, t2 = two_tenants

    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL app.current_tenant_id TO '{t1}'"))
        # Try to delete tenant B's OLTs by IP — RLS should make this a no-op.
        conn.execute(text("DELETE FROM olts WHERE ip_address = '10.0.0.1'"))

    # Verify tenant B's row is still intact.
    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL app.current_tenant_id TO '{t2}'"))
        rows = conn.execute(text("SELECT * FROM olts WHERE ip_address = '10.0.0.1'")).fetchall()
        assert len(rows) == 1
