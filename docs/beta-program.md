# Closed Beta Program — OLT Manager SaaS

## Goal

Onboard 5–10 friendly ISPs, gather concrete feedback, fix bugs, and prove
reliability before public launch.

## Beta criteria (Phase 6 entry gate)

- Phase 1–5 all green and stable on staging for 1 week with synthetic load
- All P0 bugs fixed, no known data-loss issues
- Backups verified by a real restore drill
- Runbooks for the top-5 incident classes written and pinned in `docs/runbooks/`
- Observability: Sentry receiving errors, Grafana receiving metrics, alerts firing on test conditions

## Cohort

- 5–10 ISPs the founder already knows personally
- Each gets a **90-day free trial with full Pro plan limits**
- Manual onboarding: a 30-minute Zoom to walk through signup + WireGuard install
- Dedicated Slack/Discord channel for fast feedback
- Each beta tenant has the `beta_cohort` flag set in `tenants.metadata`
  so we can filter analytics

## Telemetry

We use [PostHog](https://posthog.com) (cloud free tier or self-hosted) for
product analytics. The backend module `backend/telemetry.py` is the only
place that emits events — never call PostHog directly from a route.

### Tracked events

| Event                       | When fired                                                  |
|-----------------------------|-------------------------------------------------------------|
| `signup_completed`          | After `POST /auth/register` returns 201                     |
| `first_olt_added`           | First successful `POST /api/olts` for a tenant              |
| `workspace_wg_connected`    | First WireGuard heartbeat from the customer-side gateway    |
| `checkout_started`          | Stripe checkout session created                             |
| `subscription_activated`    | `customer.subscription.created` webhook handled             |
| `feedback_submitted`        | Feedback widget POST                                        |

### Key funnels

1. **Activation**: `signup_completed` → `first_olt_added` → `workspace_wg_connected`
2. **Conversion**: `signup_completed` → `checkout_started` → `subscription_activated`

### Dashboards

Build these in PostHog and link them from this doc once the beta starts:

- Daily active workspaces (last 30d)
- Time-to-first-OLT (median + p90)
- Time-to-WG-connected (median + p90)
- Polling success rate (from Prometheus, not PostHog)
- Beta funnel: signup → first OLT → WG connect

## Feedback loop

- **Weekly beta sync email**: 1 thing that worked, 1 thing that didn't
- **In-app widget**: every page has a "Send feedback" button → POST `/api/feedback`
- **Bug tracker**: GitHub Issues with the `beta-` label, triaged daily
- **Roadmap visibility**: Public Canny / Featurebase board so customers
  see their requests being considered

## Iteration cadence

Two-week sprints:

- **Week 1**: build features driven by feedback
- **Week 2**: stabilize, deploy, observe, write the next sprint's plan

Aim for ≥ 3 noticeable improvements per sprint.

## Exit criteria (Phase 6 → Phase 7)

- ≥ 80% of beta users say they would pay if asked (NPS-style survey)
- 0 P0 bugs open
- 99% polling success rate over the trailing 7 days
- 0 data-loss incidents
- All beta users successfully connected their workspaces via WireGuard
- Stripe billing tested with **at least 2 real charges** (not test mode)

## Beta retro template

At the end of the beta, capture in `docs/beta-retro.md`:

- What worked
- What broke
- Top 3 surprises
- Top 3 customer asks
- Decision: launch / extend beta / pivot

## Privacy

- Analytics are pseudonymous: distinct_id is `tenant:<uuid>`, never the email
- The `_scrub` helper in `backend/telemetry.py` drops PII before sending
- Customers can opt out of telemetry via a tenant-level setting (post-launch)
