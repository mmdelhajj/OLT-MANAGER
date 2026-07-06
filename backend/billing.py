"""Stripe billing integration (Phase 2.4).

Endpoints:
    POST /api/billing/checkout — create a Stripe Checkout Session, return URL
    POST /api/billing/portal   — create a Stripe Customer Portal session
    POST /webhooks/stripe      — handle subscription lifecycle events

The plan locks Stripe in as the billing provider. We don't add a payment
abstraction layer because (a) switching providers is rare and painful
either way and (b) one less abstraction = one less footgun.

Environment variables:
    STRIPE_SECRET_KEY        — sk_test_... or sk_live_...
    STRIPE_WEBHOOK_SECRET    — whsec_... (for signature verification)
    STRIPE_PRICE_STARTER     — price_... for Starter plan
    STRIPE_PRICE_PRO         — price_...
    STRIPE_PRICE_SCALE       — price_...
    APP_URL                  — e.g. https://app.oltmanager.io

Webhook idempotency: Stripe retries failed deliveries, so every handler
must be safe to replay. We use Stripe event IDs as natural idempotency
keys and short-circuit on duplicate IDs.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from email_service import send_email
from models import SessionLocal, Tenant, User
from plans import PLANS
from tenancy import TenantContext, get_tenant_context

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
APP_URL = os.getenv("APP_URL", "https://app.oltmanager.io")

# Process-local idempotency cache. Phase 5 promotes this to Redis.
_processed_events: set[str] = set()


def _stripe():
    """Lazy import — don't crash on `pip install` if stripe isn't there yet."""
    import stripe
    if STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY
    return stripe


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Checkout & customer portal
# ---------------------------------------------------------------------------


class CheckoutRequest(BaseModel):
    plan: str  # "starter" | "pro" | "scale"
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.post("/api/billing/checkout")
def create_checkout(
    payload: CheckoutRequest,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    """Create a Stripe Checkout Session for upgrading to a paid plan."""
    if payload.plan not in PLANS or payload.plan == "trial":
        raise HTTPException(status_code=400, detail="Invalid plan")
    plan = PLANS[payload.plan]
    if not plan.price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe price ID not configured for plan '{payload.plan}'",
        )

    tenant = db.query(Tenant).filter(Tenant.id == ctx.tenant_id).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    stripe = _stripe()

    # Reuse the existing Stripe customer if we have one, otherwise create.
    if not tenant.stripe_customer_id:
        customer = stripe.Customer.create(
            email=ctx.user.email,
            name=tenant.name,
            metadata={"tenant_id": tenant.id, "tenant_slug": tenant.slug},
        )
        tenant.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": plan.price_id, "quantity": 1}],
        success_url=payload.success_url or f"{APP_URL}/settings/billing?status=success",
        cancel_url=payload.cancel_url or f"{APP_URL}/settings/billing?status=cancel",
        client_reference_id=tenant.id,
        metadata={"tenant_id": tenant.id, "plan": payload.plan},
        subscription_data={"metadata": {"tenant_id": tenant.id, "plan": payload.plan}},
    )

    # Phase 6 — track funnel.
    try:
        import telemetry
        telemetry.checkout_started(tenant.id, payload.plan)
    except Exception:
        pass

    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/api/billing/portal")
def create_portal_session(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(_db),
):
    """Create a Stripe Customer Portal session for self-serve subscription mgmt."""
    tenant = db.query(Tenant).filter(Tenant.id == ctx.tenant_id).first()
    if not tenant or not tenant.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer for this tenant")
    stripe = _stripe()
    session = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=f"{APP_URL}/settings/billing",
    )
    return {"portal_url": session.url}


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


@router.post("/webhooks/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(_db),
):
    """Handle Stripe webhook events.

    Lifecycle handled:
        customer.subscription.created   -> tenant.plan = X, status = active
        customer.subscription.updated   -> tenant.plan = X
        customer.subscription.deleted   -> tenant.status = cancelled
        invoice.payment_failed          -> tenant.status = past_due, email
        invoice.payment_succeeded       -> tenant.status = active (rebound)
    """
    payload = await request.body()
    stripe = _stripe()

    if STRIPE_WEBHOOK_SECRET:
        try:
            event = stripe.Webhook.construct_event(
                payload, stripe_signature, STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.warning(f"[stripe] Bad webhook signature: {e}")
            raise HTTPException(status_code=400, detail="Invalid signature")
    else:
        # Dev mode — accept unsigned events but log loudly.
        import json
        event = json.loads(payload)
        logger.warning("[stripe] Webhook signature not configured (dev mode)")

    event_id = event.get("id") if isinstance(event, dict) else event["id"]
    event_type = event.get("type") if isinstance(event, dict) else event["type"]
    data = (event.get("data") if isinstance(event, dict) else event["data"])["object"]

    # Idempotency: drop replays we've already SUCCESSFULLY processed.
    if event_id in _processed_events:
        return {"status": "duplicate", "id": event_id}

    handler = _HANDLERS.get(event_type)
    if not handler:
        logger.info(f"[stripe] Unhandled event type: {event_type}")
        return {"status": "ignored"}

    try:
        handler(db, data)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"[stripe] Handler {event_type} failed: {e}", exc_info=True)
        # Stripe will retry on non-2xx, which is what we want for transient errors.
        raise HTTPException(status_code=500, detail="Webhook handler failed")

    # Mark processed only AFTER commit succeeds — otherwise a transient failure
    # (marked-before-run) would make Stripe's retry short-circuit as a duplicate
    # and the event would be lost forever.
    _processed_events.add(event_id)
    return {"status": "ok", "type": event_type}


# ---------------------------------------------------------------------------
# Webhook handlers
# ---------------------------------------------------------------------------


def _tenant_from_event(db: Session, data: dict) -> Optional[Tenant]:
    """Resolve a tenant from a Stripe event payload.

    Tries (in order): subscription metadata, customer id.
    """
    metadata = data.get("metadata") or {}
    tenant_id = metadata.get("tenant_id")
    if tenant_id:
        return db.query(Tenant).filter(Tenant.id == tenant_id).first()

    customer_id = data.get("customer")
    if customer_id:
        return db.query(Tenant).filter(Tenant.stripe_customer_id == customer_id).first()

    return None


def _plan_from_subscription(data: dict) -> Optional[str]:
    """Pluck the plan key out of metadata, falling back to price-id lookup."""
    metadata = data.get("metadata") or {}
    if metadata.get("plan"):
        return metadata["plan"]
    items = (data.get("items") or {}).get("data") or []
    if items:
        price_id = items[0].get("price", {}).get("id")
        for key, plan in PLANS.items():
            if plan.price_id and plan.price_id == price_id:
                return key
    return None


def _h_subscription_created(db: Session, data: dict) -> None:
    tenant = _tenant_from_event(db, data)
    if not tenant:
        logger.warning("[stripe] subscription.created with no matching tenant")
        return
    plan = _plan_from_subscription(data) or "starter"
    tenant.plan = plan
    tenant.status = "active"
    tenant.trial_ends_at = None
    logger.info(f"[stripe] Tenant {tenant.id} -> plan={plan}, status=active")
    try:
        import telemetry
        telemetry.subscription_activated(tenant.id, plan)
        telemetry.identify_tenant(tenant.id, {"plan": plan, "status": "active"})
    except Exception:
        pass


def _h_subscription_updated(db: Session, data: dict) -> None:
    tenant = _tenant_from_event(db, data)
    if not tenant:
        return
    plan = _plan_from_subscription(data)
    if plan:
        tenant.plan = plan
    sub_status = data.get("status")
    if sub_status == "active":
        tenant.status = "active"
    elif sub_status == "past_due":
        tenant.status = "past_due"
    elif sub_status in ("canceled", "cancelled", "incomplete_expired"):
        tenant.status = "cancelled"
    logger.info(f"[stripe] Tenant {tenant.id} updated -> plan={tenant.plan}, status={tenant.status}")


def _h_subscription_deleted(db: Session, data: dict) -> None:
    tenant = _tenant_from_event(db, data)
    if not tenant:
        return
    tenant.status = "cancelled"
    logger.info(f"[stripe] Tenant {tenant.id} -> cancelled")


def _h_invoice_payment_failed(db: Session, data: dict) -> None:
    tenant = _tenant_from_event(db, data)
    if not tenant:
        return
    tenant.status = "past_due"
    owner = (
        db.query(User)
        .filter(User.tenant_id == tenant.id, User.role == "owner")
        .first()
    )
    if owner:
        send_email(
            to=owner.email,
            template="payment_failed",
            context={
                "name": owner.full_name or owner.email,
                "tenant_name": tenant.name,
                "billing_url": f"{APP_URL}/settings/billing",
            },
        )
    logger.warning(f"[stripe] Tenant {tenant.id} -> past_due (payment_failed)")


def _h_invoice_payment_succeeded(db: Session, data: dict) -> None:
    tenant = _tenant_from_event(db, data)
    if not tenant:
        return
    if tenant.status == "past_due":
        tenant.status = "active"
        logger.info(f"[stripe] Tenant {tenant.id} recovered from past_due")


_HANDLERS = {
    "customer.subscription.created": _h_subscription_created,
    "customer.subscription.updated": _h_subscription_updated,
    "customer.subscription.deleted": _h_subscription_deleted,
    "invoice.payment_failed": _h_invoice_payment_failed,
    "invoice.payment_succeeded": _h_invoice_payment_succeeded,
}
