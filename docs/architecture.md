# OLT Manager — System Architecture (Phase 5+)

## High level

```
                          ┌────────────────────────┐
                          │  Customer ISP (LAN)    │
                          │                        │
                          │  ┌─────────┐           │
                          │  │  OLT    │ 192.168.… │
                          │  └────┬────┘           │
                          │       │                │
                          │  ┌────┴───────┐        │
                          │  │ WG Gateway │ ◄──────┼──── one-line install
                          │  └────┬───────┘        │
                          └───────┼────────────────┘
                                  │ WireGuard (UDP 51820)
                                  │ Workspace subnet 10.<tid>.<wid>.0/24
                                  │
                ┌─────────────────┴──────────────────┐
                │     Cloud (Fly.io / Hetzner)       │
                │                                    │
                │  ┌─────────────┐  ┌─────────────┐  │
                │  │ FastAPI app │  │ WireGuard   │  │
                │  │ (multi-tnt) │──┤ hub server  │  │
                │  └──────┬──────┘  └─────────────┘  │
                │         │                          │
                │  ┌──────┴──────┐  ┌─────────────┐  │
                │  │ Polling     │  │ Stripe      │  │
                │  │ workers     │  │ webhooks    │  │
                │  └──────┬──────┘  └─────────────┘  │
                │         │                          │
                │  ┌──────┴──────────────────────┐   │
                │  │ Managed Postgres (Neon/RDS) │   │
                │  └─────────────────────────────┘   │
                │                                    │
                │  ┌────────────────────────────┐    │
                │  │ React frontend (Vercel/CDN)│    │
                │  └────────────────────────────┘    │
                └────────────────────────────────────┘
```

## Components

### Backend (FastAPI)
- `backend/main.py` — top-level routes, polling loop, lifespan manager
- `backend/auth.py`, `backend/auth_routes.py` — JWT + bcrypt + signup/login/reset
- `backend/billing.py` — Stripe checkout, customer portal, webhooks
- `backend/plans.py` — plan limits + enforcement
- `backend/tenancy.py` — `TenantContext` dependency, RLS GUC
- `backend/wireguard/` — subnet allocator, hub manager, provisioning routes, CLI
- `backend/observability.py` — Sentry init, /health, /metrics, request middleware
- `backend/email_service.py` — provider abstraction (Postmark / Resend / SMTP / console)
- `backend/jobs/tenant_lifecycle.py` — daily trial expiry / past_due / cancellation job
- `backend/olt_drivers/` — vendor-specific OLT polling logic (Phase 0)

### Database (Postgres)
- Tenant → Workspace → Resource hierarchy
- Every business table has a denormalized `tenant_id` column for RLS
- Per-tenant Data Encryption Keys (DEKs) wrapped with the master KEK
- Migrations: `backend/migrations/versions/`
- See [data-model.md](data-model.md)

### Polling worker
- Runs in the same FastAPI process today; will move to a dedicated worker
  pool (Celery / arq) before 100 tenants
- Iterates `for tenant in active_tenants: for olt in tenant.olts:`
- Each cycle is timed and emitted to Prometheus via `observe_poll`

### WireGuard hub
- Single Linux box with a public IPv4 + UDP/51820 open
- One peer per workspace, allocated a unique /24 from `WG_SUPERNET`
- Customer-side install script handles OLT DNAT to avoid LAN collisions
- See [wireguard-hub.md](wireguard-hub.md)

### Frontend (Vite + React)
- `frontend-v2/` — new Vite/React Router 7/TanStack Query stack
- `frontend/` — legacy CRA monolith, still used by self-hosted v1.x customers
- Deploys to Vercel; talks to FastAPI via `app.oltmanager.io`

## Request flow (typical authenticated API call)

```
Browser  ──HTTPS──▶  Cloudflare ──▶  Fly.io edge ──▶  FastAPI
                                                       │
                                                       ├─ require_auth → User
                                                       ├─ get_tenant_context → TenantContext
                                                       ├─ RLS GUC set on session
                                                       └─ Postgres query (filtered by tenant_id)
```

## Deploy targets

| Env       | Backend            | DB                   | Frontend            | Stripe |
|-----------|--------------------|----------------------|---------------------|--------|
| dev       | localhost:8000     | docker postgres      | vite dev :5173      | test   |
| staging   | Fly app `staging`  | Neon free tier       | Vercel (preview)    | test   |
| prod      | Fly app `prod`     | Neon paid            | Vercel (production) | live   |

## Secrets

Set via `flyctl secrets set`. Never committed to git. See [runbooks/secrets.md](runbooks/secrets.md).

| Name                       | Purpose                                       |
|----------------------------|-----------------------------------------------|
| `DATABASE_URL`             | Pooled Postgres connection string             |
| `JWT_SECRET_KEY`           | HS256 signing key                             |
| `MASTER_ENCRYPTION_KEY`    | KEK wrapping per-tenant DEKs                  |
| `STRIPE_SECRET_KEY`        | Live Stripe API key                           |
| `STRIPE_WEBHOOK_SECRET`    | Stripe-Signature verification                 |
| `EMAIL_PROVIDER_API_KEY`   | Postmark / Resend API key                     |
| `SENTRY_DSN`               | Error reporting endpoint                      |
| `WG_HUB_PUBKEY`            | Public key of the WG hub                      |
