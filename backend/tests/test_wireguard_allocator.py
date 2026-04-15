"""Subnet allocator tests (Phase 3.2).

We use a tiny supernet (10.99.0.0/22 → four /24s) so we can exercise
exhaustion in a few iterations instead of looping over 65k candidates.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Shrink the supernet *before* the allocator module is imported.
os.environ["WG_SUPERNET"] = "10.99.0.0/22"
os.environ["WG_SUBNET_PREFIX"] = "24"

_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"

from models import Base, SessionLocal, Tenant, Workspace, engine  # noqa: E402
from wireguard import allocator  # noqa: E402

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


def _make_workspace() -> Workspace:
    db = SessionLocal()
    try:
        t = Tenant(name="Acme", slug=f"acme-{os.urandom(3).hex()}")
        db.add(t)
        db.flush()
        w = Workspace(tenant_id=t.id, name="Default")
        db.add(w)
        db.commit()
        db.refresh(w)
        return w
    finally:
        db.close()


def test_allocate_returns_valid_cidr():
    w = _make_workspace()
    db = SessionLocal()
    try:
        cidr = allocator.allocate_subnet(db, w.id)
        assert cidr.endswith("/24")
        assert cidr.startswith("10.99.")
    finally:
        db.close()


def test_allocate_is_idempotent():
    w = _make_workspace()
    db = SessionLocal()
    try:
        first = allocator.allocate_subnet(db, w.id)
        second = allocator.allocate_subnet(db, w.id)
        assert first == second
    finally:
        db.close()


def test_consecutive_allocations_get_different_subnets():
    w1 = _make_workspace()
    w2 = _make_workspace()
    db = SessionLocal()
    try:
        c1 = allocator.allocate_subnet(db, w1.id)
        c2 = allocator.allocate_subnet(db, w2.id)
        assert c1 != c2
    finally:
        db.close()


def test_release_frees_subnet_for_reuse():
    w = _make_workspace()
    db = SessionLocal()
    try:
        first = allocator.allocate_subnet(db, w.id)
        allocator.release_subnet(db, w.id)
        # New workspace, but the freed CIDR comes back into the candidate pool.
        w2 = _make_workspace()
        second = allocator.allocate_subnet(db, w2.id)
        # The first /24 in the supernet should be reused since it's the
        # earliest candidate.
        assert second == first
    finally:
        db.close()


def test_supernet_exhaustion_raises():
    """A /22 supernet has exactly four /24s — the fifth must fail."""
    db = SessionLocal()
    try:
        for _ in range(4):
            allocator.allocate_subnet(db, _make_workspace().id)

        with pytest.raises(allocator.SubnetExhaustedError):
            allocator.allocate_subnet(db, _make_workspace().id)
    finally:
        db.close()


def test_hub_and_gateway_addresses():
    cidr = "10.42.7.0/24"
    assert allocator.hub_address(cidr) == "10.42.7.1"
    assert allocator.gateway_address(cidr) == "10.42.7.2"
