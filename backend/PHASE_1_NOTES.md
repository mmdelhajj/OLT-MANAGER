# Phase 1 — Multi-Tenancy on Managed PostgreSQL

Status: foundation landed. Production binary untouched (per plan §Rollback).

## What this phase added

| Area | File(s) | Notes |
|---|---|---|
| Tenant + Workspace ORM | `models.py` | UUID PKs (String(36) for SQLite/Postgres compat), `tenant_id` denormalized to all 19 domain tables. |
| Per-tenant DEK encryption | `config.py` | `generate_tenant_dek`, `wrap_tenant_dek`, `unwrap_tenant_dek`, `encrypt_for_tenant`, `decrypt_for_tenant`. Master KEK still hardware-derived. |
| Tenant context | `tenancy.py` | `TenantContext`, `get_tenant_context`, `get_tenant_db`, `tenant_session` (background-job context manager). |
| RLS GUC plumbing | `models.py` | `set_session_tenant`, after_begin event sets `app.current_tenant_id`. No-op on SQLite. |
| Alembic migrations | `migrations/` | 0001 baseline, 0002 tenants/workspaces, 0003 backfill+rename, 0004 RLS policies. |
| Polling loop | `main.py` | New `poll_all_tenants` outer driver, `poll_all_olts` is now per-tenant scoped. Falls back to legacy single-tenant mode if `tenants` table is missing. |
| Tests | `tests/test_tenant_*.py` | 19 new tests; existing 47 still green. |

## Running the migrations

```bash
# Pick a managed Postgres provider — Neon is the cheapest dev option.
export DATABASE_URL=postgresql://user:pass@ep-xxx.neon.tech/oltmanager_dev

cd backend
venv/bin/python -m alembic upgrade head
```

The first time you run this against a fresh database it creates the
baseline schema, the tenants/workspaces tables, backfills a bootstrap
tenant + workspace, then enables Row-Level Security.

## What's intentionally NOT done in Phase 1 (matches the plan)

* The 177 `db.query()` call sites in `main.py` are NOT individually
  rewritten. They rely on Postgres RLS to enforce tenant isolation
  automatically, since every authenticated request now goes through
  `get_tenant_context` which tags the session.
* No Postgres database is provisioned — that's the user's first action
  in Phase 1 §1.2 (pick a provider, supply `DATABASE_URL`).
* No fixture data, no admin signup UI — that lands in Phase 2.
* `tunnel_manager.py` (Cloudflare) is not yet replaced — Phase 3.

## Rollback

* `alembic downgrade base` reverses 0004, 0002, 0001. **0003 is one-way** —
  see migration 0003 docstring. The existing single-tenant production
  binary is untouched throughout, so the rollback path for production is
  "do nothing".

## Phase 2 prerequisites (from §External Dependencies)

When you're ready to start Phase 2:
- [ ] Stripe account with live + test API keys
- [ ] A "Starter / Pro / Scale" product set in Stripe with price IDs
- [ ] Stripe webhook signing secret
- [ ] Email provider (Postmark / Resend / Mailgun) with API key
- [ ] Domain (`oltmanager.io` or whatever) with DNS access for SPF/DKIM/DMARC
