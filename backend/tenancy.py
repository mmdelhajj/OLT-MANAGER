"""Tenant resolution + scoping for FastAPI requests.

Phase 1 (multi-tenancy) introduces these concepts:

* Every authenticated request belongs to exactly one tenant — the tenant of
  the user who owns the JWT.
* A user has access to one or more workspaces inside that tenant.
* Database sessions are tagged with the tenant_id so PostgreSQL Row-Level
  Security policies (migration 0004) automatically filter every SELECT,
  UPDATE, and DELETE.

The functions in this module are FastAPI dependencies. Routes opt in by
declaring a parameter like::

    @app.get("/api/olts")
    def list_olts(ctx: TenantContext = Depends(get_tenant_context),
                  db: Session = Depends(get_tenant_db)):
        return db.query(OLT).all()  # already filtered by RLS

The `db.query(OLT).all()` call returns only this tenant's OLTs because the
session was tagged with `ctx.tenant_id` and Postgres RLS does the rest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import require_auth
from models import (
    SessionLocal,
    User,
    Workspace,
    set_session_tenant,
    user_workspaces,
)


@dataclass
class TenantContext:
    """Resolved tenant + workspace scope for the current request."""

    tenant_id: str
    user: User
    workspace_ids: List[str] = field(default_factory=list)
    role: str = "viewer"

    def has_workspace(self, workspace_id: str) -> bool:
        return workspace_id in self.workspace_ids

    def require_workspace(self, workspace_id: str) -> None:
        if not self.has_workspace(workspace_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Workspace not accessible",
            )


def get_tenant_db():
    """FastAPI dependency yielding a tenant-tagged DB session.

    The session must be tagged BEFORE any query runs, so callers should
    request `get_tenant_context` (which sets the tag) in the same request.
    Order of dependency resolution is not guaranteed, so we also re-apply
    the tag inside the context dependency itself.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_tenant_context(
    user: User = Depends(require_auth),
    db: Session = Depends(get_tenant_db),
) -> TenantContext:
    """Resolve the calling user's tenant + accessible workspaces.

    Raises:
        403 if the user has no tenant (data integrity bug or pre-Phase-1 user)
    """
    if not getattr(user, "tenant_id", None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no tenant assignment",
        )

    # Tag the session so this request's queries are filtered by RLS.
    set_session_tenant(db, user.tenant_id)

    # Owners and tenant-level admins implicitly see every workspace in their
    # tenant. Operators and viewers are restricted to assignments.
    if user.role in ("owner", "admin"):
        workspace_ids = [
            wid
            for (wid,) in db.query(Workspace.id).filter(
                Workspace.tenant_id == user.tenant_id
            )
        ]
    else:
        workspace_ids = [
            row.workspace_id
            for row in db.execute(
                user_workspaces.select().where(user_workspaces.c.user_id == user.id)
            )
        ]

    return TenantContext(
        tenant_id=user.tenant_id,
        user=user,
        workspace_ids=workspace_ids,
        role=user.role,
    )


def require_tenant_admin(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
    """FastAPI dependency that enforces tenant-level admin or owner role."""
    if ctx.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant admin role required",
        )
    return ctx


def require_workspace_access(workspace_id: str):
    """Build a dependency that asserts the caller has access to a workspace.

    Usage::

        @app.get("/api/workspaces/{workspace_id}/olts")
        def list_olts(workspace_id: str,
                      ctx: TenantContext = Depends(get_tenant_context)):
            ctx.require_workspace(workspace_id)
            ...
    """
    def _dep(ctx: TenantContext = Depends(get_tenant_context)) -> TenantContext:
        ctx.require_workspace(workspace_id)
        return ctx

    return _dep


# ---------------------------------------------------------------------------
# Background-worker helpers
# ---------------------------------------------------------------------------
#
# The polling loop and other background jobs don't run inside a FastAPI
# request, so they can't use the dependency above. They use this context
# manager instead:
#
#     with tenant_session(tenant.id) as db:
#         for olt in db.query(OLT): ...
#
# RLS automatically filters by tenant_id, so the loop body looks identical
# to single-tenant code.
# ---------------------------------------------------------------------------

from contextlib import contextmanager


@contextmanager
def tenant_session(tenant_id: Optional[str]):
    """Open a SQLAlchemy session pre-scoped to a tenant.

    Pass `tenant_id=None` to open an UNSCOPED session (RLS bypassed) — only
    do this for tenant-aware bootstrap code like the polling worker's outer
    `for tenant in db.query(Tenant)` loop.
    """
    db = SessionLocal()
    try:
        if tenant_id:
            set_session_tenant(db, tenant_id)
        yield db
    finally:
        db.close()
