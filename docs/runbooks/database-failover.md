# Runbook: Database failover

## Symptom
- Health check `/health` returns `{"status": "degraded", "db": "error: ..."}`
- 5xx spike in Grafana
- Sentry: `OperationalError: could not connect to server`

## Diagnosis

1. Check the Neon (or RDS) status page first:
   - Neon: https://neonstatus.com
   - AWS RDS: AWS console → RDS → instance → Events
2. From a Fly machine, try connecting directly:
   ```bash
   flyctl ssh console -a olt-manager
   psql "$DATABASE_URL" -c "SELECT 1"
   ```
3. If the primary is gone, Neon promotes a replica automatically. The
   `DATABASE_URL` Neon gives you points at the pooler endpoint, so the
   failover is transparent — but verify.

## Fix

- **Transient (< 1 min)** — wait. Most managed Postgres providers
  auto-recover within 30s.
- **Replica promoted, app cached old DNS** — restart the Fly app:
  ```bash
  flyctl apps restart olt-manager
  ```
- **Connection pool exhausted** — too many concurrent requests. Quick fix
  is restart, real fix is PgBouncer / lower `pool_size` / scale machines:
  ```bash
  flyctl scale count 4 -a olt-manager
  ```
- **Total outage** — switch to read-only mode. Set `MAINTENANCE_MODE=true`
  via `flyctl secrets set` and the app will return 503 for writes.
- **Data corruption** — stop traffic and restore from PITR. See
  [database backups](#) section in architecture.md.

## Verify
- `/health` returns `{"status": "ok", "db": "ok"}`
- Recent writes succeed (sign up a test tenant)
- p95 latency back below 500ms in Grafana

## Postmortem
- File a Neon support ticket if the failover took > 5 min
- Capture the exact `OperationalError` message and the timestamp range
