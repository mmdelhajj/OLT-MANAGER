"""Plan limits and enforcement (Phase 2.3).

Each tenant has a `plan` string that maps to one entry in PLANS. The
`enforce_plan_limit` helper raises HTTP 402 with an upgrade URL when a
tenant tries to create a resource it can't afford.

Stripe price IDs are pulled from environment variables so the same code
runs against test and live mode without code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models import OLT, ONU, Tenant, Workspace


@dataclass(frozen=True)
class Plan:
    name: str
    max_olts: int
    max_onus: int
    max_workspaces: int
    max_users: int
    price_id: Optional[str]
    monthly_usd: int


PLANS: dict[str, Plan] = {
    "trial": Plan(
        name="Trial",
        max_olts=2,
        max_onus=100,
        max_workspaces=1,
        max_users=3,
        price_id=None,
        monthly_usd=0,
    ),
    "starter": Plan(
        name="Starter",
        max_olts=5,
        max_onus=500,
        max_workspaces=2,
        max_users=5,
        price_id=os.getenv("STRIPE_PRICE_STARTER"),
        monthly_usd=49,
    ),
    "pro": Plan(
        name="Pro",
        max_olts=25,
        max_onus=5_000,
        max_workspaces=10,
        max_users=25,
        price_id=os.getenv("STRIPE_PRICE_PRO"),
        monthly_usd=199,
    ),
    "scale": Plan(
        name="Scale",
        max_olts=200,
        max_onus=100_000,
        max_workspaces=50,
        max_users=100,
        price_id=os.getenv("STRIPE_PRICE_SCALE"),
        monthly_usd=799,
    ),
}


def get_plan(tenant: Tenant) -> Plan:
    """Resolve a Tenant to its Plan, falling back to trial on unknown values."""
    return PLANS.get(tenant.plan or "trial", PLANS["trial"])


# Resource → counter function. Each function takes (db, tenant) and returns
# the current usage count for that resource within the tenant.
def _count_olts(db: Session, tenant: Tenant) -> int:
    return db.query(OLT).filter(OLT.tenant_id == tenant.id).count()


def _count_onus(db: Session, tenant: Tenant) -> int:
    return db.query(ONU).filter(ONU.tenant_id == tenant.id).count()


def _count_workspaces(db: Session, tenant: Tenant) -> int:
    return db.query(Workspace).filter(Workspace.tenant_id == tenant.id).count()


def _count_users(db: Session, tenant: Tenant) -> int:
    from models import User
    return db.query(User).filter(User.tenant_id == tenant.id).count()


_RESOURCE_LIMITS = {
    "olts": ("max_olts", _count_olts),
    "onus": ("max_onus", _count_onus),
    "workspaces": ("max_workspaces", _count_workspaces),
    "users": ("max_users", _count_users),
}


def enforce_plan_limit(db: Session, tenant: Tenant, resource: str, count_delta: int = 1) -> None:
    """Raise HTTP 402 if creating `count_delta` more `resource` would exceed
    the tenant's plan limit.

    Usage::

        enforce_plan_limit(db, ctx.tenant, "olts")  # before INSERT
    """
    if resource not in _RESOURCE_LIMITS:
        raise ValueError(f"Unknown resource for plan limit: {resource}")

    plan = get_plan(tenant)
    limit_attr, counter = _RESOURCE_LIMITS[resource]
    limit = getattr(plan, limit_attr)

    current = counter(db, tenant)
    if current + count_delta > limit:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "plan_limit_exceeded",
                "resource": resource,
                "current": current,
                "limit": limit,
                "plan": tenant.plan,
                "upgrade_url": "/settings/billing",
                "message": (
                    f"Your {plan.name} plan allows {limit} {resource}; "
                    f"you are at {current}. Upgrade to add more."
                ),
            },
        )


def plan_summary(db: Session, tenant: Tenant) -> dict:
    """Return a JSON-serializable usage report for the dashboard."""
    plan = get_plan(tenant)
    return {
        "plan": tenant.plan,
        "plan_name": plan.name,
        "monthly_usd": plan.monthly_usd,
        "limits": {
            "olts": plan.max_olts,
            "onus": plan.max_onus,
            "workspaces": plan.max_workspaces,
            "users": plan.max_users,
        },
        "usage": {
            "olts": _count_olts(db, tenant),
            "onus": _count_onus(db, tenant),
            "workspaces": _count_workspaces(db, tenant),
            "users": _count_users(db, tenant),
        },
        "status": tenant.status,
        "trial_ends_at": tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
    }
