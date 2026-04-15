# Runbook: Secrets management

## Rules

1. **Never** commit secrets to git. Pre-commit hook should reject `.env`.
2. **Never** print secrets in logs, even on error. Sentry's
   `_strip_sensitive_data` covers the obvious ones — don't add new ones
   to the redaction list as a substitute for not logging them.
3. Rotate any secret immediately if you suspect it was exposed.

## Listing current secrets

```bash
flyctl secrets list -a olt-manager
```

This shows the *names* and last-update time, never the values.

## Setting a secret

```bash
flyctl secrets set NEW_SECRET=value -a olt-manager
```

Fly will rolling-restart the app to pick up the new value.

## Rotating a secret

| Secret                  | Procedure                                            |
|-------------------------|------------------------------------------------------|
| `JWT_SECRET_KEY`        | All sessions invalidated. Notify users first.        |
| `MASTER_ENCRYPTION_KEY` | **Re-encrypt all DEKs** before flipping. See below.  |
| `STRIPE_SECRET_KEY`     | Roll in Stripe dashboard, then `flyctl secrets set`. |
| `STRIPE_WEBHOOK_SECRET` | Same — roll the endpoint, then update the secret.    |
| `SENTRY_DSN`            | Issue a new DSN in Sentry, set, restart.             |
| `EMAIL_PROVIDER_API_KEY`| Issue new key in Postmark/Resend, set, restart.      |

### Rotating the master encryption key

This is the only secret that can't be flipped instantly because every
tenant DEK is wrapped with it. Procedure:

1. Generate a new master key.
2. Run the migration:
   ```bash
   flyctl ssh console -a olt-manager
   python -m jobs.rotate_master_key --new-key <new>
   ```
   This decrypts every `tenants.dek_encrypted` with the old key and
   re-encrypts it with the new one inside a single DB transaction.
3. `flyctl secrets set MASTER_ENCRYPTION_KEY=<new>` — Fly restarts the app.
4. Verify `/health` is green and a test tenant can decrypt OLT credentials.

## Reading a secret value (rare)

`flyctl` deliberately doesn't expose this. If you absolutely need it:
```bash
flyctl ssh console -a olt-manager -C 'printenv SECRET_NAME'
```
Use sparingly and never share over chat.
