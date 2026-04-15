"""Phase 5 — observability hooks: Sentry, structured logging, metrics, health.

Everything in this module is optional. If a dependency isn't installed (sentry-sdk,
prometheus-client) we degrade gracefully so dev environments without observability
keep booting. Production environments install the deps and set the env vars.

Wire it up from `main.py` after `app = FastAPI(...)`:

    from observability import setup_observability
    setup_observability(app)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import FastAPI, Request, Response

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentry
# ---------------------------------------------------------------------------


def init_sentry() -> None:
    """Initialise Sentry if SENTRY_DSN is set. No-op otherwise.

    Call this as early as possible in main.py — *before* `app = FastAPI(...)` —
    so the FastAPI integration can hook into request handling.
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration
    except ImportError:
        logger.warning(
            "SENTRY_DSN is set but sentry-sdk is not installed. "
            "Run: pip install 'sentry-sdk[fastapi]'"
        )
        return

    environment = os.getenv("ENVIRONMENT", "development")
    release = os.getenv("RELEASE_VERSION") or os.getenv("FLY_IMAGE_REF", "unknown")

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        # Lower sample rate in prod, full coverage in staging.
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),
        send_default_pii=False,  # Never send tenant data to Sentry
        integrations=[
            FastApiIntegration(),
            StarletteIntegration(),
            SqlalchemyIntegration(),
        ],
        before_send=_strip_sensitive_data,
    )
    logger.info(f"Sentry initialised for environment={environment} release={release}")


def _strip_sensitive_data(event, hint):
    """Scrub anything that smells like a secret before shipping to Sentry."""
    sensitive_keys = {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "stripe_secret_key",
        "wg_privkey",
        "wg_privkey_enc",
        "dek_encrypted",
    }

    def scrub(obj):
        if isinstance(obj, dict):
            return {
                k: ("[REDACTED]" if k.lower() in sensitive_keys else scrub(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [scrub(item) for item in obj]
        return obj

    if "request" in event and isinstance(event["request"], dict):
        event["request"] = scrub(event["request"])
    if "extra" in event:
        event["extra"] = scrub(event["extra"])
    return event


# ---------------------------------------------------------------------------
# Prometheus metrics
# ---------------------------------------------------------------------------


_REGISTRY = None
_HTTP_REQUESTS = None
_HTTP_DURATION = None
_TENANTS_GAUGE = None
_OLTS_GAUGE = None
_POLL_DURATION = None


def _init_metrics() -> None:
    """Set up Prometheus metric objects. Idempotent."""
    global _REGISTRY, _HTTP_REQUESTS, _HTTP_DURATION
    global _TENANTS_GAUGE, _OLTS_GAUGE, _POLL_DURATION

    if _REGISTRY is not None:
        return

    try:
        from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry
    except ImportError:
        logger.info("prometheus-client not installed; /metrics will be a stub")
        return

    _REGISTRY = CollectorRegistry()
    _HTTP_REQUESTS = Counter(
        "oltmgr_http_requests_total",
        "Total HTTP requests",
        ["method", "path", "status"],
        registry=_REGISTRY,
    )
    _HTTP_DURATION = Histogram(
        "oltmgr_http_request_duration_seconds",
        "HTTP request duration",
        ["method", "path"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
        registry=_REGISTRY,
    )
    _TENANTS_GAUGE = Gauge(
        "oltmgr_tenants_total",
        "Number of tenants by status",
        ["status"],
        registry=_REGISTRY,
    )
    _OLTS_GAUGE = Gauge(
        "oltmgr_olts_total",
        "Number of OLTs across all tenants",
        registry=_REGISTRY,
    )
    _POLL_DURATION = Histogram(
        "oltmgr_poll_duration_seconds",
        "Polling cycle duration per tenant",
        ["tenant_id"],
        buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
        registry=_REGISTRY,
    )


def _normalised_path(request: Request) -> str:
    """Use the matched route template (e.g. /api/olts/{olt_id}) instead of
    the literal URL so we don't end up with a metric per OLT id."""
    route = request.scope.get("route")
    if route is not None and hasattr(route, "path"):
        return route.path  # type: ignore[no-any-return]
    return request.url.path


def metrics_response() -> Response:
    """Return Prometheus exposition format for /metrics."""
    if _REGISTRY is None:
        return Response("prometheus-client not installed\n", media_type="text/plain")
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    return Response(generate_latest(_REGISTRY), media_type=CONTENT_TYPE_LATEST)


def observe_poll(tenant_id: str, duration_seconds: float) -> None:
    """Called by the polling worker after each tenant cycle."""
    if _POLL_DURATION is not None:
        _POLL_DURATION.labels(tenant_id=str(tenant_id)).observe(duration_seconds)


# ---------------------------------------------------------------------------
# Health checks
# ---------------------------------------------------------------------------


def _check_db() -> tuple[bool, Optional[str]]:
    """Best-effort DB liveness check. Returns (ok, error_message)."""
    try:
        from models import SessionLocal
        from sqlalchemy import text

        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:  # pragma: no cover - depends on real DB
        return False, str(exc)


# ---------------------------------------------------------------------------
# FastAPI wiring
# ---------------------------------------------------------------------------


def setup_observability(app: FastAPI) -> None:
    """Attach /health, /metrics and the request-timing middleware to `app`.

    Idempotent: safe to call once at startup. Sentry is initialised in
    `init_sentry()` separately because it must run *before* the FastAPI
    object is constructed.
    """
    _init_metrics()

    @app.middleware("http")
    async def _track_requests(request: Request, call_next):
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = time.perf_counter() - start
            if _HTTP_REQUESTS is not None:
                _HTTP_REQUESTS.labels(
                    method=request.method,
                    path=_normalised_path(request),
                    status="500",
                ).inc()
            if _HTTP_DURATION is not None:
                _HTTP_DURATION.labels(
                    method=request.method, path=_normalised_path(request)
                ).observe(duration)
            raise

        duration = time.perf_counter() - start
        if _HTTP_REQUESTS is not None:
            _HTTP_REQUESTS.labels(
                method=request.method,
                path=_normalised_path(request),
                status=str(response.status_code),
            ).inc()
        if _HTTP_DURATION is not None:
            _HTTP_DURATION.labels(
                method=request.method, path=_normalised_path(request)
            ).observe(duration)
        return response

    @app.get("/health", include_in_schema=False)
    def _health():
        """Liveness + DB readiness for k8s/Fly checks."""
        db_ok, db_err = _check_db()
        return {
            "status": "ok" if db_ok else "degraded",
            "db": "ok" if db_ok else f"error: {db_err}",
            "version": os.getenv("RELEASE_VERSION", "dev"),
        }

    @app.get("/metrics", include_in_schema=False)
    def _metrics():
        return metrics_response()
