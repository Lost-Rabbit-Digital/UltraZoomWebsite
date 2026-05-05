---
title: "Where Ultra Zoom works for real estate: Zillow, Redfin, MLS, and the long tail"
description: "Which real estate sites and MLS image viewers Ultra Zoom supports out of the box, how the selector system handles the long tail of regional MLSs, and how to report a viewer that needs work."
date: 2026-04-29
category: "Use cases"
---

The most common question realtors ask us before installing is some version of *does this work with my MLS?* It's a fair question — there are hundreds of regional MLSs in the US alone, and a hover-zoom extension that works on Zillow but breaks on the system you actually use every morning is not useful.

Here's the honest answer, organized by what we've tested, what we know works, and how we handle the long tail.

## Confirmed working

**Consumer real estate sites** — Ultra Zoom works on:

- Zillow (search grid, listing pages, photo gallery)
- Redfin (search grid, listing pages, photo gallery)
- Realtor.com (search grid, listing pages, photo gallery)
- Trulia
- Homes.com

**Commercial real estate** — confirmed working on:

- CoStar
- LoopNet
- CREXI

**Major MLS image viewers** — the underlying viewer software powers most regional MLSs, and Ultra Zoom works on the common ones (FlexMLS, Matrix, Paragon, Rapattoni's image gallery). If your MLS uses one of those, the extension behaves the way it does on Zillow: hover the thumbnail, get the full image at resolution.

## The selector system, in plain English

Ultra Zoom doesn't ship a hand-rolled integration for every MLS. There are too many of them, and most of them update their viewers on a quiet schedule we can't track.

Instead, the extension works on two layers:

1. **Per-site plugins** for the high-volume sites (Zillow, Redfin, Realtor.com, the major MLS viewers above). These are tuned to the way each site lays out its image grid, so hover-zoom feels native — including in the lightbox modal and during arrow-key gallery navigation.
2. **Generic image detection** for everything else. The extension finds image elements on the page, identifies which one your cursor is over, and pulls the highest-resolution version available. This is what makes Ultra Zoom work on most regional MLSs even when we haven't seen them — most viewers are using a small set of underlying frameworks under the hood.

In practice, this means a regional MLS we've never tested usually works on first install. When it doesn't, it's almost always because the viewer is using an unusual lazy-loading pattern or a CSS background image instead of an `img` element. Both are fixable with a small selector update.

## What "doesn't work" actually looks like

If a site is genuinely incompatible, you'll see one of two things:

- **No zoom appears on hover.** Ultra Zoom isn't finding an image element to attach to. This usually means the site is rendering photos as CSS backgrounds or canvas elements.
- **Zoom appears but the image is blurry.** Ultra Zoom is finding the thumbnail but not the high-resolution variant. This is almost always a `srcset` or lazy-load pattern we haven't taught the extension about.

Both are quick to fix once we know about them. Neither is catastrophic — at worst, the site behaves as if Ultra Zoom isn't installed.

## How to report an MLS that needs work

If your MLS is in the second bucket, send us a note. We need three things:

1. The MLS name (the formal one — "Bright MLS," "CRMLS," "Stellar MLS," etc.)
2. A screenshot or screen recording of the broken behavior
3. Whether your MLS access is gated — i.e., whether we'd need credentials or whether there's a public demo or sample listing we can hit

Email [boden@lostrabbitdigital.com](mailto:boden@lostrabbitdigital.com) or use the [contact form](/contact). MLS image viewer fixes are usually a same-week turnaround. If your access is gated, we can either work from the recording you send or arrange a 20-minute screen-share to verify the fix on your account.

## The credential problem

The reason we don't pre-test every regional MLS is the same reason hover-zoom extensions historically broke on them: most MLSs require active agent credentials to log in, and we don't have a hundred of those.

Two ways realtors have helped us close this gap:

- **Free lifetime Pro accounts** to agents who run a 20-minute compatibility test on their MLS via screen-share. If you're up for that, the offer is open.
- **Sample-listing URLs.** A handful of MLSs expose at least one public-facing demo listing for marketing or recruiting purposes. If you know yours does, send us the URL and we can verify selectors against it without needing credentials.

## Per-site control

A small note that comes up often: Ultra Zoom has a per-site toggle in the toolbar popup. If your MLS has its own lightbox you prefer, you can flip Ultra Zoom off on that one site and keep it running everywhere else. No reinstall, no settings page detour. The same toggle is useful when a site has unusual zoom behavior of its own that you don't want to override.

## Try it on your stack

The honest test is the one you run yourself: [install Ultra Zoom](/realtors?coupon=REALTOR30), open the sites you actually use during a buyer search or CMA, and see whether it disappears into the workflow. If it doesn't, tell us what broke and we'll fix it. Realtors get 30% off Pro forever with `REALTOR30` — but the free tier covers most agent workflows, and you can decide whether Pro pays for itself in the first afternoon of use.
