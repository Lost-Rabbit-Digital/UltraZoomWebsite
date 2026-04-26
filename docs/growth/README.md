# Ultra Zoom — Website Growth Work

Companion to the master growth plan in `ultrazoom/growth/README.md`. This doc covers only the work that lands in **this repo** (marketing website + per-repo Worker deploys).

## Summary of website-side scope

| Feature | Route(s) added | Backend needed | Effort in this repo |
|---|---|---|---|
| F4 Watermark | `pricing` bullet only | No | XS |
| F2 Prompts | Optional `/review` redirector | No | XS |
| F7 Shareable Zoom | `/z/[id]` | Yes (external Worker) | M |
| F1 Feedback-for-Pro | `/feedback`, `/feedback/thanks` | Yes (external Worker) | S |
| F3 Referrals | `/r/[code]` | Yes (external Worker) | S |

## Shared infra touches in this repo

- **Cookie script** (S3 attribution): a ~20-line inline `<script>` in the default layout that reads URL query `src`, `code`, `r`, `z` and sets a first-party `uz_src` cookie for 90 days. Needed by F7, F3, and F1 attribution.
- **Install CTA component**: a shared Astro component (`src/components/InstallCTA.astro`) that renders Chrome + Firefox buttons, browser-detects, and appends the current-page attribution query (`?src=...`). Used by F7/F3/F1 landing pages.
- **Cloudflare Worker bindings**: the website repo's `wrangler.jsonc` currently has no KV/D1/R2. Backend state (share links, feedback submissions, referral codes) lives on the **existing Worker** at `api.ultrazoom.app` in the `ultrazoom` repo. This website calls those endpoints via `fetch()`, so this repo needs no new bindings.

## Per-feature pointers

See the extension-repo docs for full specs. Below, only the marketing-site responsibilities.

### F7 — Shareable Zoom (`/z/[id]`)
- `src/pages/z/[id].astro` — SSR, fetches share metadata from `api.ultrazoom.app/api/z/:id`.
- Client-side extension detection via `postMessage` handshake (see extension doc).
- `noindex` on result pages; OG card uses the blurred teaser.
- "Report this link" button → `POST api.ultrazoom.app/api/z/:id/report`.

### F1 — Feedback (`/feedback`)
- `src/pages/feedback.astro` — tabbed form (T1 chat / T2 video / T3 interview).
- Posts to `api.ultrazoom.app/api/feedback`.
- T3 tab embeds Cal.com (or mailto fallback MVP).
- `src/pages/feedback/thanks.astro` — confirmation.

### F3 — Referrals (`/r/[code]`)
- `src/pages/r/[code].astro` — invite landing, sets `uz_src` cookie with `{ src: 'referral', code }`.
- Uses the shared `InstallCTA` component.

### F4 / F2 — Minor
- F4: add "Watermark-free exports" to the `/pricing` Pro feature list.
- F2: optional `/review` redirector page that detects browser and 302s to the correct store review URL. A tiny Astro page, client-side JS.

## Build order (matches master plan)

1. **F4** — pricing page bullet only (1-line change).
2. **F2** — `/review` redirector (XS).
3. **Shared**: cookie script + `InstallCTA` component.
4. **F7** — `/z/[id]` + extension-detect handshake.
5. **F1** — `/feedback`.
6. **F3** — `/r/[code]`.

## Cross-cutting

- **No new tracking pixels**. If we want page-view analytics, Plausible or Cloudflare Web Analytics (zero-cookie) only.
- **Styling**: all new pages match the existing dark-theme `public/styles.css`. No Tailwind in this repo.
- **Preview pipeline**: each new route needs a Playwright smoke test.

## Open questions for this repo

- **Analytics**: today there is none. Do we add Plausible/CF Web Analytics before shipping F7 so we can measure top-of-funnel?
- **Bindings for caching?** If the `/z/*` SSR paths generate enough traffic, we may want a KV binding here for edge-caching metadata fetched from the API Worker. Defer until we see load.
- **Email capture**: F1 needs it. Do we add a newsletter tool (ConvertKit/Buttondown) to this repo, or keep email capture on the API Worker side?
