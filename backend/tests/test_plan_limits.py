"""Tests for plan limit enforcement (Phase 2.3)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from models import Base, OLT, Tenant, Workspace  # noqa: E402
from plans import PLANS, enforce_plan_limit, get_plan, plan_summary  # noqa: E402


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    try:
        yield s
    finally:
        s.close()
        engine.dispose()


def _trial_tenant(db) -> Tenant:
    t = Tenant(name="Acme", slug="acme", plan="trial", status="trial")
    db.add(t)
    db.flush()
    db.add(Workspace(tenant_id=t.id, name="Default"))
    db.flush()
    return t


def test_get_plan_falls_back_to_trial_for_unknown():
    fake = type("T", (), {"plan": "made-up"})()
    assert get_plan(fake).name == "Trial"


def test_trial_plan_allows_first_olt(db):
    t = _trial_tenant(db)
    enforce_plan_limit(db, t, "olts")  # 0 -> 1, OK


def test_trial_plan_blocks_third_olt(db):
    t = _trial_tenant(db)
    w = db.query(Workspace).filter(Workspace.tenant_id == t.id).first()
    for i in range(2):  # trial allows 2
        db.add(OLT(
            tenant_id=t.id, workspace_id=w.id,
            name=f"olt{i}", ip_address=f"10.0.0.{i}",
            username="admin", password="ENC:x",
        ))
    db.flush()

    with pytest.raises(HTTPException) as exc:
        enforce_plan_limit(db, t, "olts")
    assert exc.value.status_code == 402
    assert exc.value.detail["error"] == "plan_limit_exceeded"
    assert exc.value.detail["resource"] == "olts"
    assert exc.value.detail["limit"] == 2


def test_pro_plan_allows_more(db):
    t = _trial_tenant(db)
    t.plan = "pro"
    db.flush()
    # Pro allows 25 OLTs — adding 5 should succeed.
    enforce_plan_limit(db, t, "olts", count_delta=5)


def test_plan_summary_shape(db):
    t = _trial_tenant(db)
    summary = plan_summary(db, t)
    assert summary["plan"] == "trial"
    assert summary["plan_name"] == "Trial"
    assert "limits" in summary and "usage" in summary
    assert summary["limits"]["olts"] == 2
    assert summary["usage"]["olts"] == 0


def test_unknown_resource_raises_value_error(db):
    t = _trial_tenant(db)
    with pytest.raises(ValueError):
        enforce_plan_limit(db, t, "rocketships")
