import { defineConfig } from "astro/config";
import tailwind from "@astrojs/tailwind";

// Astro config for the OLT Manager marketing site (Phase 7).
// Deployed to Vercel / Netlify / Cloudflare Pages — entirely static.
export default defineConfig({
  site: "https://oltmanager.io",
  integrations: [tailwind()],
});
