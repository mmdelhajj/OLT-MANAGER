"""Public auth API for the SaaS (Phase 2.1, 2.2).

Endpoints:
    POST /auth/register         — create tenant + first user, send verify email
    POST /auth/login            — issue JWT (delegates to existing auth logic)
    POST /auth/forgot-password  — issue reset token, send reset email
    POST /auth/reset-password   — consume reset token, set new password
    POST /auth/verify-email     — consume verify token, mark email verified
    GET  /auth/me               — return current user + tenant + plan summary

The plan locked these in fastapi-users-style names. We don't pull
fastapi-users in (it's a heavyweight dep) — instead we reuse the existing
bcrypt + JWT helpers from auth.py and add the missing pieces here.
"""
from __future__ import annotations

import logging
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from auth import (
    authenticate_user,
    create_access_token,
    get_password_hash,
    validate_password_strength,
)
from config import generate_tenant_dek, wrap_tenant_dek
from email_service import send_email
from models import SessionLocal, Tenant, User, Workspace
from plans import plan_summary

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

TRIAL_DAYS = 14
RESET_TOKEN_TTL = timedelta(hours=1)
VERIFY_TOKEN_TTL = timedelta(days=7)
SLUG_RE = re.compile(r"[^a-z0-9-]+")

# In-memory token stores. Phase 5 will move these to Redis or a
# `password_resets` / `email_verifications` table — for now they live in
# the FastAPI process, which is fine because there's only one process per
# region in early-stage SaaS deployments.
_reset_tokens: dict[str, tuple[str, datetime]] = {}  # token -> (user_id, expires)
_verify_tokens: dict[str, tuple[str, datetime]] = {}


def _db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _slugify(name: str) -> str:
    base = SLUG_RE.sub("-", name.strip().lower()).strip("-") or "tenant"
    return base[:50]


def _unique_slug(db: Session, base: str) -> str:
    candidate = base
    suffix = 0
    while db.query(Tenant).filter(Tenant.slug == candidate).first():
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


def _issue_token_for(store: dict, user_id: str, ttl: timedelta) -> str:
    token = secrets.token_urlsafe(32)
    store[token] = (user_id, datetime.utcnow() + ttl)
    return token


def _consume_token(store: dict, token: str) -> Optional[str]:
    record = store.pop(token, None)
    if not record:
        return None
    user_id, expires = record
    if expires < datetime.utcnow():
        return None
    return user_id


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    # No min_length here — we run validate_password_strength in the route so
    # we can return a structured 400 with a human-readable reason instead of
    # Pydantic's 422.
    password: str
    company_name: str = Field(min_length=2, max_length=200)
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    tenant_id: str
    role: str
    workspace_id: Optional[str] = None
    wg_cidr: Optional[str] = None
    wg_config: Optional[str] = None  # full wg-quick blob
    mikrotik_script: Optional[str] = None  # RouterOS 7 script
    agent_key: Optional[str] = None  # plaintext agent key (shown once at signup)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(_db)):
    """Self-serve signup: creates Tenant + Workspace + owner User in one tx."""
    valid, message = validate_password_strength(payload.password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    # Email uniqueness is per-tenant, but for signup we want it globally
    # unique so the same person can't accidentally create two trial tenants
    # with the same address. Phase 6 may relax this for invited users.
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=409, detail="Email already in use")

    slug = _unique_slug(db, _slugify(payload.company_name))

    dek = generate_tenant_dek()
    tenant = Tenant(
        name=payload.company_name,
        slug=slug,
        plan="trial",
        status="trial",
        trial_ends_at=datetime.utcnow() + timedelta(days=TRIAL_DAYS),
        dek_encrypted=wrap_tenant_dek(dek),
    )
    db.add(tenant)
    db.flush()

    # The tenant exists now, so set the RLS GUC for the rest of this
    # transaction so subsequent INSERTs (workspace, user) pass the
    # tenant_isolation policy. SET LOCAL is scoped to the current tx.
    from sqlalchemy import text as _sql_text
    from models import is_postgres
    if is_postgres():
        db.execute(_sql_text(f"SET LOCAL app.current_tenant_id = '{tenant.id}'"))

    workspace = Workspace(tenant_id=tenant.id, name="Default")
    db.add(workspace)
    db.flush()

    user = User(
        tenant_id=tenant.id,
        email=payload.email,
        password_hash=get_password_hash(payload.password),
        role="owner",
        full_name=payload.full_name,
        is_active=True,
    )
    db.add(user)
    db.flush()

    # Grant the owner access to the default workspace.
    from models import user_workspaces, set_session_tenant
    db.execute(
        user_workspaces.insert().values(
            user_id=user.id, workspace_id=workspace.id, role="admin"
        )
    )

    # Tag the session with the new tenant_id so the after_begin hook
    # re-applies `app.current_tenant_id` on every subsequent transaction
    # in this request. provision_workspace below calls allocate_subnet,
    # which commits — without re-tagging, the next UPDATE on `workspaces`
    # would fail RLS because SET LOCAL was scoped to the original tx.
    set_session_tenant(db, tenant.id)

    # Provision WireGuard peer for the new workspace. If provisioning
    # fails (e.g. subnet allocator exhausted) the user still gets their
    # tenant — we log the failure and let them retry from the dashboard.
    wg_cidr = None
    wg_config_blob = None
    wg_mikrotik_script = None
    try:
        from wireguard.manager import provision_workspace, render_mikrotik_script
        peer = provision_workspace(db, workspace, tenant)
        wg_cidr = peer.cidr
        wg_config_blob = peer.config_blob
        wg_mikrotik_script = render_mikrotik_script(
            cidr=peer.cidr,
            private_key=peer.private_key,
            workspace_name=workspace.name,
            tenant_name=tenant.name,
        )
    except Exception as exc:
        logger.exception("WireGuard provisioning failed during signup: %s", exc)

    # Capture the values we need *after* the commit so we don't have to
    # re-fetch through RLS (which would require the session to be tagged
    # with the new tenant_id first).
    # Auto-generate an agent API key so the customer can set up their
    # local agent immediately after signup. The plaintext key is included
    # in the signup response (shown once in the dashboard).
    agent_raw_key = None
    try:
        import hashlib as _hl
        from models import AgentKey
        _agent_raw = "agk_" + secrets.token_hex(24)
        _agent_hash = _hl.sha256(_agent_raw.encode()).hexdigest()
        agent_key_row = AgentKey(
            tenant_id=tenant.id,
            workspace_id=workspace.id,
            key_hash=_agent_hash,
            key_prefix=_agent_raw[:8],
            name="Default Agent",
        )
        db.add(agent_key_row)
        agent_raw_key = _agent_raw
    except Exception as _ak_err:
        logger.warning("Agent key auto-generation failed: %s", _ak_err)

    new_user_id = user.id
    new_user_email = user.email
    new_user_full_name = user.full_name
    new_tenant_id = tenant.id
    new_tenant_name = tenant.name
    new_workspace_id = workspace.id

    db.commit()

    # set_session_tenant was already called above (before WG provisioning)
    # so any subsequent reads on this Session continue to pass RLS.

    # Email verification (best-effort — failure does not block signup)
    verify_token = _issue_token_for(_verify_tokens, new_user_id, VERIFY_TOKEN_TTL)
    try:
        send_email(
            to=new_user_email,
            template="verify_email",
            context={
                "tenant_name": new_tenant_name,
                "verify_url": f"https://app.oltmanager.io/verify-email/{verify_token}",
            },
        )
        send_email(
            to=new_user_email,
            template="welcome",
            context={
                "name": new_user_full_name or new_user_email,
                "tenant_name": new_tenant_name,
                "plan": "Trial",
                "trial_days": TRIAL_DAYS,
                "app_url": "https://app.oltmanager.io",
            },
        )
    except Exception:
        # Email provider not configured yet — never block signup on this.
        pass

    token = create_access_token({"user_id": new_user_id, "tenant_id": new_tenant_id})

    # Phase 6 — fire-and-forget product analytics. Never let telemetry
    # break a signup, hence the broad except.
    try:
        import telemetry
        telemetry.identify_tenant(
            new_tenant_id,
            {"plan": "trial", "status": "trial", "slug": slug},
        )
        telemetry.signup_completed(new_tenant_id, "trial")
    except Exception:
        pass

    return TokenResponse(
        access_token=token,
        user_id=new_user_id,
        tenant_id=new_tenant_id,
        role="owner",
        workspace_id=new_workspace_id,
        wg_cidr=wg_cidr,
        wg_config=wg_config_blob,
        mikrotik_script=wg_mikrotik_script,
        agent_key=agent_raw_key,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(_db)):
    """Email + password → JWT.

    Multi-tenant note: a global email lookup is sufficient because we
    enforce email uniqueness across tenants at signup time (see
    /auth/register). The user's tenant_id comes from the row.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Reuse the existing rate-limited authenticate_user, but it expects
    # `username` so we shim by setting it before the call.
    authed = authenticate_user(db, payload.email, payload.password)
    if not authed:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"user_id": authed.id, "tenant_id": authed.tenant_id})
    return TokenResponse(
        access_token=token,
        user_id=authed.id,
        tenant_id=authed.tenant_id,
        role=authed.role,
    )


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(_db)):
    """Always returns 202 to avoid leaking which emails are registered."""
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token = _issue_token_for(_reset_tokens, user.id, RESET_TOKEN_TTL)
        send_email(
            to=user.email,
            template="reset_password",
            context={
                "reset_url": f"https://app.oltmanager.io/reset-password/{token}",
            },
        )
    return {"status": "ok"}


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(_db)):
    user_id = _consume_token(_reset_tokens, payload.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    valid, message = validate_password_strength(payload.password)
    if not valid:
        raise HTTPException(status_code=400, detail=message)

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = get_password_hash(payload.password)
    user.failed_login_attempts = 0
    user.locked_until = None
    db.commit()
    return {"status": "ok"}


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(_db)):
    user_id = _consume_token(_verify_tokens, payload.token)
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid or expired token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.email_verified_at = datetime.utcnow()
    db.commit()
    return {"status": "verified"}


@router.get("/me")
def me(db: Session = Depends(_db), tenant_ctx=Depends(__import__("tenancy", fromlist=["get_tenant_context"]).get_tenant_context)):
    """Return the current user, their tenant, and plan/usage summary."""
    user = tenant_ctx.user
    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

    # Agent connection status
    agent_status = []
    try:
        from models import AgentKey
        now = datetime.utcnow()
        keys = db.query(AgentKey).filter(
            AgentKey.tenant_id == user.tenant_id,
            AgentKey.is_active == True,
        ).all()
        for k in keys:
            is_connected = (
                k.last_seen_at is not None
                and (now - k.last_seen_at).total_seconds() < 120
            )
            agent_status.append({
                "workspace_id": k.workspace_id,
                "is_connected": is_connected,
                "last_seen_at": k.last_seen_at.isoformat() if k.last_seen_at else None,
                "agent_version": k.agent_version,
            })
    except Exception:
        pass

    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "email_verified": user.email_verified_at is not None,
        },
        "tenant": {
            "id": tenant.id,
            "name": tenant.name,
            "slug": tenant.slug,
            "status": tenant.status,
        },
        "workspaces": tenant_ctx.workspace_ids,
        "billing": plan_summary(db, tenant),
        "agents": agent_status,
    }
