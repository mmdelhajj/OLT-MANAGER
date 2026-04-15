# Public Launch Checklist (Phase 7)

Use this list as the final gate before opening public signups. Every
item must be checked off, with the responsible person and the date.

## Product

- [ ] All Phase 1–6 verification checks still pass
- [ ] Marketing site live at `oltmanager.io`
- [ ] Docs site live at `docs.oltmanager.io`
- [ ] Status page live at `status.oltmanager.io`
- [ ] Pricing finalized and matches `backend/plans.py`
- [ ] Trial flow works end-to-end (signup → email verify → checkout → active)
- [ ] All beta-feedback P0/P1 issues resolved

## Legal & Compliance

- [ ] Terms of Service drafted and reviewed by a lawyer
- [ ] Privacy Policy drafted and reviewed by a lawyer
- [ ] Cookie banner installed (GDPR)
- [ ] DPA template available for enterprise customers
- [ ] Data deletion request process documented (GDPR Art. 17)

## Email Deliverability

- [ ] SPF record set
- [ ] DKIM signing enabled
- [ ] DMARC policy at `p=quarantine` minimum
- [ ] `mail-tester.com` score ≥ 9/10 from production sending domain
- [ ] Bounce + complaint webhooks wired into PostHog or Slack

## Infrastructure

- [ ] Postgres on paid Neon tier with PITR enabled
- [ ] Daily logical backup to off-provider storage (Backblaze B2)
- [ ] Backup restore drill completed in last 30 days
- [ ] Cloudflare in front of `app.oltmanager.io` with DDoS rules
- [ ] WAF rules for `/auth/login` and `/auth/register` rate limiting
- [ ] Sentry receiving real production errors (test event captured)
- [ ] Grafana dashboards saved + linked from `docs/runbooks/README.md`

## Operations

- [ ] On-call rotation documented (even if it's just one person)
- [ ] PagerDuty / OpsGenie / email alerts wired
- [ ] All runbooks in `docs/runbooks/` reviewed within last 30 days
- [ ] `/health` returns 200 from prod
- [ ] `flyctl secrets list` audited — no stale entries

## Customer Operations

- [ ] Support inbox set up: `support@oltmanager.io`
- [ ] In-app onboarding checklist working for new tenants
- [ ] Welcome email sequence triggers on signup
- [ ] Beta cohort migrated to paid plans
- [ ] Public Canny / Featurebase board for feature requests

## Vendor Drivers

- [ ] At least 1 non-VSOL driver shipped (Phase 7.5 target: Huawei MA5800)
- [ ] Vendor onboarding doc lists all supported models
- [ ] CLI fixtures captured and committed for every supported vendor

## Launch Day

- [ ] Launch post drafted (Hacker News / r/networking / LinkedIn)
- [ ] Beta customers given a 24h heads-up that public launch is happening
- [ ] On-call engineer in front of dashboard for the first 4 hours
- [ ] Decision tree for "what if traffic 10x's?" — documented before, not after

## Post-launch (Day 1)

- [ ] First 24h metrics captured: signups, conversions, errors, p95 latency
- [ ] Sentry triaged daily for the first week
- [ ] Customer support response SLA met (4h business hours)
- [ ] Retro scheduled for Day 14
