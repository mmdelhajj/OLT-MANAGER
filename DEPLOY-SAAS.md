# SaaS Deploy Checklist (2026-07 audit fixes)

Consolidates the deploy-relevant changes from the July 2026 code audit
(commits `8ab2434` … `7d924f3`). Run on the SaaS server (`157.90.101.28` /
`remotolt.ltd`, Postgres). Do it in a maintenance window.

## 1. Back up first
```bash
source /etc/olt-manager.env
pg_dump "$DATABASE_URL" > /root/oltmanager-$(date +%F-%H%M).sql
```

## 2. Pull code
```bash
cd /opt/olt-manager && git pull origin main
```

## 3. Apply DB migrations (CRITICAL — new required schema)
```bash
cd /opt/olt-manager/backend && source /etc/olt-manager.env
venv/bin/python -m alembic upgrade head
```
Adds: `0008` olts.snmp_community · `0009` **agent_keys table** (agent endpoints
were 500ing without it) · `0010` **olts.mk_*** columns (OLT queries errored
without them) · `0011` poll-path indexes · `0012` users.is_staff.

## 4. One-time: dedupe duplicate ONU rows (Postgres)
The startup `dedupe_onus()` only runs on the local SQLite build — RLS blocks the
unscoped query on Postgres. Run once, per tenant. Example (psql):
```sql
-- keep the online / most-recent row per (olt_id, mac_address), delete the rest
-- + their traffic_history. Do inside a tenant-scoped session or as a SECURITY
-- DEFINER helper. TEST on the backup first.
```
(If you want, I can write the exact tenant-scoped dedupe script.)

## 5. Restart + verify
```bash
systemctl restart olt-manager && sleep 3 && systemctl is-active olt-manager
# agent_keys exists + mk_ columns present:
venv/bin/python -c "import os,sqlalchemy as sa; e=sa.create_engine(os.environ['DATABASE_URL']); i=sa.inspect(e); print('agent_keys:', i.has_table('agent_keys')); print('mk cols:', [c['name'] for c in i.get_columns('olts') if c['name'].startswith('mk_')])"
```

## 6. Env vars to confirm (SECURITY)
- **`STRIPE_WEBHOOK_SECRET` MUST be set** — otherwise the webhook is fail-open
  (anyone can POST to upgrade their tenant). The handler now marks events
  processed only after commit (retries no longer lost).
- **`WG_SUPERNET`** must be the SAME value everywhere (allocator + hub). Default
  drift (`10.0.0.0/8` vs `10.99.0.0/16`) breaks tunnels.

## 7. WireGuard onboarding change — TEST BEFORE RE-ISSUING
The Mikrotik onboarding script now scopes to the workspace's own /24 + hub /32
(was the whole /16 → cross-tenant reachability). **Validate against ONE real
customer router before re-issuing to everyone.** Also add a hub-side
`wg0 → wg0` forward-drop (hub config, not in this repo) for defense-in-depth.
Existing already-connected routers keep their old (wide) config until re-onboarded.

## 8. Behavioural changes to expect (good)
- Plan limits now enforced on create-OLT and agent ingest (402 / skip past limit).
- Agent buffers+retries failed pushes; won't push faster than 10s.
- Poll loop no longer freezes/storms on first poll or hot OLT.
- Offline ONUs read 0; graphs UTC-tagged + 30-day retention; Mikrotik overlay
  works on GPON; 32-bit-only OLTs now report traffic.

## Still OPEN (not in this deploy)
- **Frontend rx/tx (download/upload) inverted** — needs a SaaS-frontend rebuild.
- **Scheduled Tasks** never execute — no dispatcher (needs task_type contract).
- `traffic_snapshots` lacks a unique constraint (dual-writer dupes) — deferred.
- LOW tail: default admin/admin seed, unpinned TLS to OLT web, fabricated
  CPU/RAM/traffic jitter in the UI.
