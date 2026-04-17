---
title: "The bundle budget we actually ship"
description: "A line-by-line look at what Ultra Zoom ships to every user, why each piece is there, and where the bytes are going."
date: 2026-04-17
category: "Engineering"
---

Browser extensions are easy to under-think. The popup is small, the options page is small, and nobody's asking you to hit a Lighthouse score. So developers reach for their usual stack and never look at the bundle.

We look at ours. Here's what Ultra Zoom ships, broken out by what loads when.

## The short version

Our built extension — everything that goes into the `.crx` Chrome downloads — is about **1.6 MB on disk**. Roughly half of that is a promotional GIF we ship with the welcome page. The JavaScript total is **188 KB uncompressed** across 24 files, and the CSS total is **55 KB**.

But "total bundle size" is the wrong frame for an extension. Nobody loads all of it at once. What matters is which bytes run on which surface, and how often that surface is hit.

## What ships on every page

The content script is the only thing that loads on every page where Ultra Zoom is active. That's the byte budget we care about most:

| File | Raw | Gzipped |
|---|---|---|
| `hoverzoom.ts` (content script) | 58.1 KB | 18.4 KB |
| `hoverzoom.css` | 7.8 KB | 2.2 KB |

**20.6 KB gzipped, per page.** That's the cost of opening a tab with Ultra Zoom enabled. The browser parses and executes it before any hover interaction is possible.

Inside that 58 KB are the hover detection loop, the overlay renderer, the keyboard shortcut handler, settings reads from `chrome.storage.local`, and the free-tier universal CDN matchers (imgur, Cloudfront, generic `img srcset` parsing). No framework runtime — the content script is plain TypeScript over DOM APIs. It has to be: running Preact on every tab would be a much harder sell.

## What ships on a toolbar click

The popup is the second-hottest surface. Click the toolbar icon and the browser loads:

| File | Raw | Gzipped |
|---|---|---|
| `popup-*.js` | 6.6 KB | 2.4 KB |
| `hooks.module-*.js` (Preact hooks) | 14.1 KB | 5.8 KB |
| `popup-*.css` (Tailwind) | 27.9 KB | 5.4 KB |
| Preact runtime (shared chunk) | ~11 KB | ~4 KB |

Roughly **18 KB of JS gzipped** to render six toggles, a search box, and a supported-site indicator. The Preact runtime and hooks module are shared with the options page, so only one of the two pays the framework cost on first load — whichever you open first.

The CSS is the ugly number. 27.9 KB of Tailwind for a popup is a lot of utility classes for not-a-lot of UI. We've looked at PurgeCSS tuning and shaved it down from ~60 KB, but the current number reflects a build that keeps variants we actually use (dark mode, hover states, focus-visible). Further shrinkage is possible; it hasn't been worth the review time yet.

## What ships on the options page

The options page is the most feature-dense surface: toggles, keyboard shortcut editor, custom rules, Pro settings, license key input.

| File | Raw | Gzipped |
|---|---|---|
| `options-*.js` | 40.3 KB | 10.2 KB |
| `custom-rules-*.js` (lazy chunk) | 17.5 KB | 5.4 KB |
| `constants-*.js` (shared) | 10.1 KB | 3.1 KB |
| `options-*.css` (Tailwind) | 27.8 KB | 5.3 KB |

The custom-rules editor is code-split — if a user never opens that tab, the 17.5 KB doesn't load. This kind of per-route splitting is cheap with Vite and worth doing even on a small surface.

## What ships as Pro plugins

Each premium site (Instagram, TikTok, Pixiv, LinkedIn, Flickr, eBay, YouTube, etc.) is its own code-split chunk:

| Plugin | Raw | Gzipped |
|---|---|---|
| `vk.js` | 0.5 KB | 0.4 KB |
| `steam.js` | 0.8 KB | 0.4 KB |
| `facebook.js` | 0.9 KB | 0.5 KB |
| `ebay.js` | 1.4 KB | 0.7 KB |
| `tiktok.js` | 1.9 KB | 0.8 KB |
| `flickr.js` | 1.9 KB | 1.0 KB |
| `pixiv.js` | 2.0 KB | 0.9 KB |
| `youtube.js` | 2.6 KB | 1.3 KB |
| `deviantart.js` | 2.7 KB | 1.3 KB |
| `instagram.js` | 2.7 KB | 1.3 KB |
| `twitch.js` | 3.0 KB | 1.4 KB |
| `linkedin.js` | 3.5 KB | 1.4 KB |

A plugin only loads when the user is actually on that site. Instagram's plugin is ~1.3 KB gzipped; it does nothing on Reddit. Per-site plugins are small because most of the complexity — overlay rendering, keyboard handling, settings — lives in the content script they plug into.

## What ships as the service worker

The MV3 service worker is the background coordinator: license validation, message routing, storage events.

| File | Raw | Gzipped |
|---|---|---|
| `service-worker.ts` | 6.4 KB | 2.6 KB |

It's small because it does small things. No DOM, no rendering, no framework. We wrote earlier about [the MV3 trap](/blog/manifest-v3-trap) — part of surviving MV3 is accepting that the service worker has to be a coordinator, not an app.

## What ships as images

Everything non-code in the extension is images, and images dominate the on-disk total:

- `ultra-zoom-google-example.gif` — 842 KB (welcome page demo)
- `ultra_zoom_screen_1.png` through `_4.png` — 422 KB combined
- Icons (16/48/128) — 16 KB

The GIF is the biggest single file we ship. It's only loaded on the welcome page, shown once at install time. Moving it to a streamed `video` element or hosting it off the extension would save ~840 KB on the download, at the cost of requiring network access at welcome time. We've decided the install-time download cost is worth paying for an offline-capable welcome experience. It's a real tradeoff, not an oversight.

## The totals, honestly

If you install Ultra Zoom today, you download about **1.6 MB**. Of that:

- **~860 KB** is images (dominated by the welcome GIF)
- **188 KB** is JavaScript across 24 files
- **55 KB** is CSS
- **The rest** is manifest, icons, and HTML shells

If you use the extension (open a tab with a supported site), the code that actually runs is:

- **20.6 KB gzipped** of content script + CSS, always
- **~18 KB gzipped** of popup, once per toolbar click (cached after)
- **~18 KB gzipped** of options, only if you open settings
- **~1 KB gzipped** of per-site plugin, only on that site

That's the budget. It's not zero — we ship a UI framework (Preact) and a utility CSS system (Tailwind) — but the per-page cost is bounded, the per-site cost is pay-as-you-go, and nothing in the hot path imports a framework.

## How we keep it honest

Three habits:

**Build output is in version control conversations, not just artifacts.** Every PR that touches UI gets its bundle size noted in the description. Bundle growth without a feature to justify it is a review comment.

**Code-split by surface, not by component.** The popup, options, welcome, and service worker are separate entry points. Per-site plugins are their own chunks. This isn't about optimizing for one user — it's about making sure a change to the options page doesn't bloat what ships on every tab.

**Images are treated like code.** The welcome GIF has a size budget. If we add a second demo image, something else has to shrink or move off-device. Images are easy to forget about and the single biggest lever in the total.

There is nothing clever here. We measure what we ship, we split by what loads when, and we push back on growth. For an extension that lives on every page, that's the whole job.
