# OLT Manager — Public Documentation Site

This will live at `https://docs.oltmanager.io` once Phase 7 ships.

## Stack

We use [Starlight](https://starlight.astro.build/) (Astro-based docs theme).
It's static, fast, accepts plain Markdown, and ships with search.

## Bootstrap

```bash
npm create astro@latest -- --template starlight docs-site
cd docs-site
npm install
npm run dev
```

The bootstrap was deferred to avoid checking in 50+ MB of generated
template files. Run the command above when you're ready to start
populating real content.

## Sections to write

| Section            | Source material                                  |
|--------------------|--------------------------------------------------|
| Quickstart         | 5-minute happy path: signup → workspace → OLT    |
| OLT Setup          | Per-vendor: VSOL, Huawei, ZTE                    |
| WireGuard          | Inline copy of `docs/wireguard-hub.md`           |
| API Reference      | Auto-generated from FastAPI's `/openapi.json`    |
| Plans & Billing    | Mirror of `backend/plans.py`                     |
| FAQ                | Pulled from beta program feedback                |
| Troubleshooting    | Subset of `docs/runbooks/` aimed at customers    |
| Changelog          | Mirrors GitHub releases                          |

## Auto-generated API reference

```bash
# In CI:
curl https://app.oltmanager.io/openapi.json > docs-site/src/content/api/openapi.json
npx @scalar/cli reference --spec docs-site/src/content/api/openapi.json --output dist/api
```

## Style

- Short sentences. Code-first. No marketing fluff (that's the marketing
  site's job).
- Every page has a "Was this helpful?" widget that posts to PostHog.
- Run links and code blocks against staging at least once before publishing.
