# Runbook: Stripe webhook stuck

## Symptom
- Stripe dashboard → Developers → Webhooks shows red error counts
- Customer reports "I paid but still see the trial banner"
- Sentry: `Stripe webhook signature verification failed`

## Diagnosis

1. In the Stripe dashboard, pull the failing event ID.
2. Check what the backend logged:
   ```bash
   flyctl logs -a olt-manager | grep <event_id>
   ```
3. Common causes:
   - **Signature failure** → `STRIPE_WEBHOOK_SECRET` doesn't match the endpoint
   - **5xx response** → application bug; Sentry will have the trace
   - **Timeout** → endpoint took > 10s; likely DB hang or external call
   - **Idempotency replay** → duplicate event, safely ignored if seen recently

## Fix

- **Wrong webhook secret** — copy the current value from Stripe:
  ```bash
  flyctl secrets set STRIPE_WEBHOOK_SECRET=whsec_xxx -a olt-manager
  ```
- **Application bug** — fix the bug, deploy, then in Stripe:
  Developers → Webhooks → "Resend" the failed event(s)
- **Timeout** — investigate why the handler is slow; the webhook should
  hand off to a background task within 1s if anything is non-trivial
- **Manual reconciliation** — if the customer paid but their tenant didn't
  upgrade, fix it directly:
  ```sql
  UPDATE tenants SET plan = 'pro', status = 'active'
  WHERE stripe_customer_id = 'cus_xxx';
  ```
  Then file an issue to find out why the webhook didn't do this.

## Verify
- Stripe dashboard shows the event as `succeeded`
- `tenant.plan` matches the Stripe subscription
- Customer's billing page shows the correct plan

## Postmortem
- Add the failing event payload to `tests/test_billing.py` as a regression
- If signature failures, audit how `STRIPE_WEBHOOK_SECRET` got out of sync
