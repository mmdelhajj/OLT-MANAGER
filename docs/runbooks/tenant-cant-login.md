# Runbook: Tenant says they can't log in

## Symptom
- Customer email or chat: "I can't sign in"
- HTTP 401 from `/auth/login`, or 403 on subsequent calls

## Diagnosis

1. Get the tenant's email. Look it up in Postgres:
   ```sql
   SELECT u.id, u.email, u.email_verified, u.locked_until,
          t.id AS tenant_id, t.status, t.deleted_at
   FROM users u JOIN tenants t ON u.tenant_id = t.id
   WHERE u.email = '<email>';
   ```
2. Check each likely cause in order:
   - `t.deleted_at IS NOT NULL` → tenant was soft-deleted
   - `t.status = 'cancelled'` → trial expired or subscription cancelled
   - `t.status = 'past_due'` → payment failed; auth still works but features gated
   - `u.email_verified = false` → user never clicked the verification link
   - `u.locked_until > NOW()` → bcrypt rate limiter triggered

## Fix

- **Soft-deleted tenant** — restore:
  ```sql
  UPDATE tenants SET deleted_at = NULL, status = 'active' WHERE id = '<id>';
  ```
- **Cancelled tenant** — verify they paid in Stripe; if so, the webhook
  failed. See [stripe-webhook-stuck.md](stripe-webhook-stuck.md).
- **Unverified email** — resend verification:
  ```bash
  flyctl ssh console -a olt-manager
  python -c "from auth_routes import resend_verification; resend_verification('<email>')"
  ```
- **Locked account** — clear the lock:
  ```sql
  UPDATE users SET locked_until = NULL, failed_login_attempts = 0 WHERE id = '<id>';
  ```

## Verify
- Customer logs in successfully
- `SELECT last_login FROM users WHERE id = '<id>'` shows a recent timestamp

## Postmortem
- If you fixed a webhook race, file an issue and add the event to the
  idempotency replay test
- If multiple customers hit the same lock, raise the bcrypt threshold or
  add CAPTCHA
