"""Phase 6 — in-app feedback collection.

Customers see a "Send feedback" widget in the dashboard. This module
exposes:

* `POST /api/feedback`     — authenticated, anyone in a tenant
* `GET  /api/feedback`     — list this tenant's own submissions
* `GET  /admin/feedback`   — owner-only across-tenant view (support team)

Submissions are also forwarded to PostHog as a `feedback_submitted` event
so the user can see beta engagement at a glance.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import telemetry
from models import Feedback, SessionLocal
from tenancy import TenantContext, get_tenant_context

logger = logging.getLogger(__name__)

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


VALID_CATEGORIES = {"bug", "idea", "praise", "other"}


class FeedbackIn(BaseModel):
    category: str = Field(..., description="bug | idea | praise | other")
    message: str = Field(..., min_length=3, max_length=4000)
    page_url: Optional[str] = Field(None, max_length=500)


class FeedbackOut(BaseModel):
    id: str
    category: str
    message: str
    page_url: Optional[str]
    created_at: str

    class Config:
        from_attributes = True


@router.post("/api/feedback", response_model=FeedbackOut, status_code=201)
def submit_feedback(
    payload: FeedbackIn,
    request: Request,
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> FeedbackOut:
    """Persist a feedback row and ping PostHog."""
    if payload.category not in VALID_CATEGORIES:
        raise HTTPException(
            status_code=400,
            detail=f"category must be one of {sorted(VALID_CATEGORIES)}",
        )

    user_agent = request.headers.get("user-agent", "")[:500]

    fb = Feedback(
        tenant_id=str(ctx.tenant_id),
        user_id=str(ctx.user.id),
        category=payload.category,
        message=payload.message,
        page_url=payload.page_url,
        user_agent=user_agent,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    try:
        telemetry.feedback_submitted(str(ctx.tenant_id), payload.category)
    except Exception as exc:  # pragma: no cover - telemetry must never break the request
        logger.warning(f"telemetry feedback_submitted failed: {exc}")

    return FeedbackOut(
        id=fb.id,
        category=fb.category,
        message=fb.message,
        page_url=fb.page_url,
        created_at=fb.created_at.isoformat(),
    )


@router.get("/api/feedback", response_model=list[FeedbackOut])
def list_my_feedback(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[FeedbackOut]:
    """List feedback submitted by anyone in the caller's tenant."""
    rows = (
        db.query(Feedback)
        .filter(Feedback.tenant_id == str(ctx.tenant_id))
        .order_by(Feedback.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        FeedbackOut(
            id=r.id,
            category=r.category,
            message=r.message,
            page_url=r.page_url,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/admin/feedback", response_model=list[FeedbackOut])
def list_all_feedback(
    ctx: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
) -> list[FeedbackOut]:
    """Cross-tenant feedback list. Restricted to internal staff users.

    A 'staff' user is one whose `is_staff` flag is true. The flag is set
    manually in the DB — there's deliberately no UI for it because we
    don't want customers granting themselves admin access.
    """
    if not getattr(ctx.user, "is_staff", False):
        raise HTTPException(status_code=403, detail="staff only")

    rows = (
        db.query(Feedback)
        .order_by(Feedback.created_at.desc())
        .limit(500)
        .all()
    )
    return [
        FeedbackOut(
            id=r.id,
            category=r.category,
            message=r.message,
            page_url=r.page_url,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
