# OLT Manager — Marketing Site

Astro static site, deployed to Vercel / Netlify / Cloudflare Pages.

## Develop

```bash
cd marketing-site
npm install
npm run dev   # http://localhost:4321
```

## Deploy

```bash
npm run build      # outputs to dist/
```

Configure your host's "static site" project to:

- Build command: `npm run build`
- Output directory: `dist`
- Install command: `npm install`

## Sources of truth

- **Pricing** — copied from `backend/plans.py`. Update both at the same time.
- **Vendor list** — copied from `backend/olt_drivers/registry.py`.
- **CTAs** — every "Sign up" button must point at `https://app.oltmanager.io/signup`.

## Adding a page

Drop a `.astro` file in `src/pages/`. Astro picks it up automatically.

## TODO before launch

- [ ] Replace placeholder copy with marketing-approved wording
- [ ] Add Open Graph / Twitter Card images
- [ ] Add `/terms` and `/privacy` pages reviewed by a lawyer
- [ ] Cookie banner (GDPR)
- [ ] PostHog snippet for visitor analytics
- [ ] Sitemap + robots.txt
