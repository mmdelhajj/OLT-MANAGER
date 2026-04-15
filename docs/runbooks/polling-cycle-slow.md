# Runbook: Polling cycle slow

## Symptom
- Grafana alert: `oltmgr_poll_duration_seconds > 60` for 5 minutes
- Customers report stale ONU status
- Backend logs: `Polling cycle for tenant <id> took 87.4s`

## Diagnosis

1. Find the slowest tenants:
   ```promql
   topk(5, oltmgr_poll_duration_seconds_bucket{le="+Inf"})
   ```
2. SSH and inspect their OLT count:
   ```bash
   flyctl ssh console -a olt-manager
   psql "$DATABASE_URL" -c "
     SELECT t.id, t.name, COUNT(o.id) AS olts
     FROM tenants t LEFT JOIN olts o ON o.tenant_id = t.id
     GROUP BY t.id ORDER BY olts DESC LIMIT 10;
   "
   ```
3. Common causes:
   - One tenant has 100+ OLTs and the per-tenant loop is sequential
   - WireGuard handshake is slow / timing out
   - SNMP retries against an unreachable OLT eat the cycle
   - The DB is slow (see [database-failover.md](database-failover.md))

## Fix

- **One huge tenant** — temporarily increase that tenant's polling
  interval, file an issue to move polling to a dedicated worker pool
- **Unreachable OLT** — disable polling for that OLT until the customer
  fixes connectivity:
  ```sql
  UPDATE olts SET polling_enabled = false WHERE id = <id>;
  ```
- **Hub overloaded** — scale the WG hub vertically; the per-peer
  cryptography is CPU-bound
- **Long-term fix** — move polling to Celery/arq with one queue per
  tenant. Tracked in the Phase 5+ followups.

## Verify
- `oltmgr_poll_duration_seconds` p95 back below 30s
- ONU status freshness < 60s in the dashboard

## Postmortem
- Capture which tenants were affected and for how long
- Decide whether to bump the dedicated-worker work item up the backlog
