"""Stripe webhook tests (Phase 2.4).

We don't talk to real Stripe — instead we craft webhook payloads in the
shape Stripe would send, dispatch them through the FastAPI route, and
assert the tenant lifecycle transitions are correct.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_db_file.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_db_file.name}"
# Disable signature verification for the dev mode codepath.
os.environ.pop("STRIPE_WEBHOOK_SECRET", None)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import billing  # noqa: E402
from billing import router as billing_router  # noqa: E402
from models import Base, SessionLocal, Tenant, engine  # noqa: E402

Base.metadata.create_all(bind=engine)


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(billing_router)
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset():
    billing._processed_events.clear()
    with engine.begin() as conn:
        for tbl in reversed(Base.metadata.sorted_tables):
            try:
                conn.execute(tbl.delete())
            except Exception:
                pass
    yield


def _make_tenant(plan="trial", status="trial", customer_id=None) -> Tenant:
    db = SessionLocal()
    try:
        t = Tenant(
            name="Acme",
            slug=f"acme-{uuid.uuid4().hex[:6]}",
            plan=plan,
            status=status,
            stripe_customer_id=customer_id,
        )
        db.add(t)
        db.commit()
        db.refresh(t)
        return t
    finally:
        db.close()


def _post_event(client, event_type, data, event_id=None):
    payload = {
        "id": event_id or f"evt_{uuid.uuid4().hex}",
        "type": event_type,
        "data": {"object": data},
    }
    return client.post(
        "/webhooks/stripe",
        content=json.dumps(payload),
        headers={"content-type": "application/json"},
    )


def test_subscription_created_activates_tenant(client):
    t = _make_tenant(customer_id="cus_test_123")
    r = _post_event(
        client,
        "customer.subscription.created",
        {"customer": "cus_test_123", "metadata": {"tenant_id": t.id, "plan": "pro"}},
    )
    assert r.status_code == 200
    db = SessionLocal()
    try:
        refreshed = db.query(Tenant).filter(Tenant.id == t.id).first()
        assert refreshed.plan == "pro"
        assert refreshed.status == "active"
    finally:
        db.close()


def test_subscription_updated_changes_plan(client):
    t = _make_tenant(plan="starter", status="active", customer_id="cus_456")
    r = _post_event(
        client,
        "customer.subscription.updated",
        {
            "customer": "cus_456",
            "status": "active",
            "metadata": {"tenant_id": t.id, "plan": "scale"},
        },
    )
    assert r.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(Tenant).filter(Tenant.id == t.id).first().plan == "scale"
    finally:
        db.close()


def test_subscription_deleted_cancels_tenant(client):
    t = _make_tenant(plan="pro", status="active", customer_id="cus_789")
    r = _post_event(
        client,
        "customer.subscription.deleted",
        {"customer": "cus_789", "metadata": {"tenant_id": t.id}},
    )
    assert r.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(Tenant).filter(Tenant.id == t.id).first().status == "cancelled"
    finally:
        db.close()


def test_payment_failed_sets_past_due(client):
    t = _make_tenant(plan="pro", status="active", customer_id="cus_pay")
    r = _post_event(
        client,
        "invoice.payment_failed",
        {"customer": "cus_pay", "metadata": {"tenant_id": t.id}},
    )
    assert r.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(Tenant).filter(Tenant.id == t.id).first().status == "past_due"
    finally:
        db.close()


def test_payment_succeeded_recovers_past_due(client):
    t = _make_tenant(plan="pro", status="past_due", customer_id="cus_rec")
    r = _post_event(
        client,
        "invoice.payment_succeeded",
        {"customer": "cus_rec", "metadata": {"tenant_id": t.id}},
    )
    assert r.status_code == 200
    db = SessionLocal()
    try:
        assert db.query(Tenant).filter(Tenant.id == t.id).first().status == "active"
    finally:
        db.close()


def test_webhook_idempotent_on_replay(client):
    """Replaying the same event id must not double-apply state changes."""
    t = _make_tenant(plan="trial", status="trial", customer_id="cus_idem")
    event_id = "evt_idem_001"
    body = {
        "customer": "cus_idem",
        "metadata": {"tenant_id": t.id, "plan": "pro"},
    }
    r1 = _post_event(client, "customer.subscription.created", body, event_id=event_id)
    r2 = _post_event(client, "customer.subscription.created", body, event_id=event_id)
    assert r1.status_code == 200
    assert r2.json()["status"] == "duplicate"


def test_unknown_event_type_is_ignored(client):
    r = _post_event(client, "customer.something.weird", {})
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"
