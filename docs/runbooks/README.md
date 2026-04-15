# Runbooks

Operational procedures for the OLT Manager SaaS. Keep them short, scannable,
and tested. Each runbook should answer:

1. **Symptom** — what does the user / monitor see?
2. **Diagnosis** — how do you confirm the cause?
3. **Fix** — exact commands to run
4. **Verify** — how to confirm the issue is resolved
5. **Postmortem** — what to capture if it's a repeat

| Runbook                                              | When                                             |
|------------------------------------------------------|--------------------------------------------------|
| [tenant-cant-login.md](tenant-cant-login.md)         | A customer reports they can't sign in            |
| [wireguard-tunnel-down.md](wireguard-tunnel-down.md) | A workspace's WG status is `stale` or `pending`  |
| [stripe-webhook-stuck.md](stripe-webhook-stuck.md)   | Webhook delivery failures in Stripe dashboard    |
| [database-failover.md](database-failover.md)         | Postgres primary unreachable                     |
| [polling-cycle-slow.md](polling-cycle-slow.md)       | Poll duration alert firing                       |
| [secrets.md](secrets.md)                             | Rotating / setting / reading secrets safely      |
