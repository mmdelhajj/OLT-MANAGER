"""Phase 6 — product analytics via PostHog.

Anonymous (or pseudonymous) event tracking for the beta. Always opt-in:
the customer's tenant has a `telemetry_enabled` flag and we never send
PII without explicit consent.

Usage from a route handler:

    from telemetry import track
    track(ctx.tenant_id, "olt_added", {"vendor": "vsol", "model": "V1600D8"})

If POSTHOG_API_KEY isn't set, every call is a silent no-op so dev /
self-hosted environments aren't affected.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

_client = None
_disabled = False


def _get_client():
    """Lazy-init the PostHog client. Returns None if PostHog isn't installed
    or the API key isn't configured."""
    global _client, _disabled
    if _disabled:
        return None
    if _client is not None:
        return _client

    api_key = os.getenv("POSTHOG_API_KEY", "").strip()
    if not api_key:
        _disabled = True
        return None

    try:
        from posthog import Posthog
    except ImportError:
        logger.info("posthog not installed; telemetry disabled")
        _disabled = True
        return None

    host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
    _client = Posthog(api_key, host=host)
    logger.info(f"PostHog telemetry enabled (host={host})")
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def track(
    tenant_id: str,
    event: str,
    properties: Optional[dict[str, Any]] = None,
    user_id: Optional[str] = None,
) -> None:
    """Record a product analytics event for a tenant.

    The distinct_id is the tenant_id (not the user_id) so we can see
    tenant-level behaviour without identifying individual operators.
    Pass user_id explicitly only when you need to attribute an action
    to a specific operator (rare).
    """
    client = _get_client()
    if client is None:
        return

    payload: dict[str, Any] = {
        "tenant_id": str(tenant_id),
        "$lib": "oltmgr-backend",
    }
    if properties:
        payload.update(_scrub(properties))

    distinct_id = str(user_id) if user_id else f"tenant:{tenant_id}"
    try:
        client.capture(distinct_id=distinct_id, event=event, properties=payload)
    except Exception as exc:
        logger.warning(f"telemetry capture failed for event={event}: {exc}")


def identify_tenant(tenant_id: str, properties: dict[str, Any]) -> None:
    """Attach tenant-level properties (plan, status, signup date)."""
    client = _get_client()
    if client is None:
        return
    try:
        client.group_identify(
            group_type="tenant",
            group_key=str(tenant_id),
            properties=_scrub(properties),
        )
    except Exception as exc:
        logger.warning(f"telemetry identify failed: {exc}")


def shutdown() -> None:
    """Flush pending events. Call from FastAPI's shutdown handler."""
    if _client is not None:
        try:
            _client.shutdown()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_PII_KEYS = {
    "email",
    "password",
    "token",
    "ip_address",
    "phone",
    "full_name",
    "stripe_customer_id",
    "wg_privkey",
}


def _scrub(properties: dict[str, Any]) -> dict[str, Any]:
    """Drop anything that might be PII so we never send it to PostHog."""
    return {
        k: v for k, v in properties.items()
        if k.lower() not in _PII_KEYS
    }


# ---------------------------------------------------------------------------
# Convenient event helpers — call these instead of stringly-typed track()
# so the event taxonomy stays consistent.
# ---------------------------------------------------------------------------


def signup_completed(tenant_id: str, plan: str) -> None:
    track(tenant_id, "signup_completed", {"plan": plan})


def first_olt_added(tenant_id: str, vendor: str, model: str) -> None:
    track(tenant_id, "first_olt_added", {"vendor": vendor, "model": model})


def workspace_wg_connected(tenant_id: str, workspace_id: str) -> None:
    track(
        tenant_id,
        "workspace_wg_connected",
        {"workspace_id": str(workspace_id)},
    )


def checkout_started(tenant_id: str, plan: str) -> None:
    track(tenant_id, "checkout_started", {"plan": plan})


def subscription_activated(tenant_id: str, plan: str) -> None:
    track(tenant_id, "subscription_activated", {"plan": plan})


def feedback_submitted(tenant_id: str, category: str) -> None:
    track(tenant_id, "feedback_submitted", {"category": category})
