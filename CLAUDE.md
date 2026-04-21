# CLAUDE.md — Ultra Zoom Website

## Project Overview

Marketing and documentation website for the Ultra Zoom browser extension. Built with Astro and deployed to Cloudflare Workers.

**URL:** https://ultrazoom.app (Cloudflare Workers)
**Publisher:** Lost Rabbit Digital LLC

## Architecture

```
src/
  layouts/
    BaseLayout.astro   Shared layout (head, nav, footer)
  pages/
    index.astro        Landing page
    help.astro         Setup guide, keyboard shortcuts, supported sites
    blog.astro         Blog post listings
    contact.astro      Contact form (Formspree)
    privacy.astro      Privacy policy
    terms.astro        Terms of use
    success.astro      Post-payment confirmation
public/
  styles.css           Central stylesheet (dark theme, responsive)
  images/              Icons and assets
wrangler.jsonc         Cloudflare Workers config (static assets from dist/)
astro.config.mjs       Astro configuration
scripts/
  find-leads.mjs       Dork-driven lead discovery (Google CSE → CSV)
.github/
  workflows/
    static.yml         CI pipeline
    record-scroll.yml  Promotional video recording (Playwright)
  lighthouse/
    lighthouserc.json  Lighthouse CI config
  scripts/             Automation scripts
docs/
  diagrams/            Mermaid diagram source files
  growth/              Growth plan notes
  outreach/            Outreach leads, drafts, prompts, contact-form templates
```

## Technology Stack

- **Astro** — static site generator, outputs to `dist/`
- **Dark theme** — GitHub-inspired color scheme (`#0d1117` background, `#58a6ff` brand blue)
- **Hosting:** Cloudflare Workers (static assets served from `dist/`)
- **Deploy:** `npx wrangler versions upload` (configured in `wrangler.jsonc`)

## Pages

| Page | File | Purpose |
|------|------|---------|
| Home | `src/pages/index.astro` | Landing page with install buttons, features, pricing |
| Help | `src/pages/help.astro` | Setup guide, keyboard shortcuts, supported sites |
| Blog | `src/pages/blog.astro` | Blog post listings |
| Contact | `src/pages/contact.astro` | Contact form |
| Privacy | `src/pages/privacy.astro` | Privacy policy |
| Terms | `src/pages/terms.astro` | Terms of use |
| Success | `src/pages/success.astro` | Post-payment confirmation (noindex) |

## Development

```bash
npm install          # Install dependencies
npm run dev          # Start dev server (localhost:4321)
npm run build        # Build to dist/
npm run preview      # Preview production build
```

## Deployment

Cloudflare Workers builds on push. The build pipeline:
1. `npm install` (auto-detected)
2. `npm run build` (build command — produces `dist/`)
3. `npx wrangler versions upload` (deploy command — serves `dist/` as static assets)

**Important:** In Cloudflare dashboard, set Build command to `npm run build`.

## Design Tokens

```css
--bg-primary:    #0d1117
--bg-secondary:  #161b22
--brand:         #58a6ff
--text-primary:  #e6edf3
--text-secondary:#8b949e
--border:        #30363d
--success:       #3fb950
--error:         #f85149
```

## Conventions

- All styling in `public/styles.css` — no inline styles, no CSS modules
- Shared layout in `src/layouts/BaseLayout.astro` — header, nav, footer
- Semantic HTML with accessibility focus (skip links, ARIA labels, focus indicators)
- Inline scripts use `<script is:inline>` to prevent Astro bundling
- Images served from `public/images/`
- Internal links use clean paths (`/help`, `/blog`) not `.html` extensions
