---
title: "Zero-knowledge by design: how Ultra Zoom handles your data"
description: "A detailed look at Ultra Zoom's data architecture: what stays on your machine, what crosses the network, and what is never collected or sent."
date: 2026-04-12
category: "Privacy & security"
---

"Zero knowledge" gets thrown around a lot in tech marketing. For Ultra Zoom, it means something specific: we architected the extension so that we *cannot* see what you browse, even if we wanted to. This post explains exactly how that works.

## Three buckets: local, network, and never

Every piece of data Ultra Zoom touches falls into one of three categories. No exceptions.

### 1. Stays on your machine

These are stored in your browser's local extension storage. They never leave your device.

- **Per-site preferences:** your customized settings for individual websites
- **Site toggles:** which sites you've enabled or disabled Ultra Zoom on
- **Hover history:** purely local; used only for the "recently viewed" feature
- **Usage statistics:** counts and timestamps that power the extension's internal dashboards, visible only to you
- **License cache:** a cached copy of your license status so we don't have to re-check it on every page load

None of this data is synced to a server, included in crash reports, or transmitted anywhere. It lives in `chrome.storage.local` (or the Firefox equivalent) and it stays there.

### 2. Crosses the network

Only two types of network requests ever leave your browser:

- **Image requests, direct to the origin server.** When you hover a thumbnail, Ultra Zoom fetches the full-resolution image from the same server that hosts the website. This is the same request your browser would make if you clicked the image and opened it in a new tab. Ultra Zoom doesn't proxy these through our servers or any third party.
- **License check, once at activation.** When you first activate a paid license, Ultra Zoom validates the key against our licensing server. After that, the result is cached locally. This is a single HTTPS request containing only the license key. No browsing data, no device fingerprints, no usage telemetry.

That's it. Two categories. You can verify this yourself by opening your browser's developer tools (F12 → Network tab) and watching the traffic while you use Ultra Zoom.

### 3. Never sent anywhere

These data points are explicitly *not* collected, stored on our servers, or transmitted:

- **Hovered image URLs:** we don't log which images you view
- **Browsing history:** we have no visibility into the pages you visit
- **Telemetry and analytics:** there's no analytics SDK, no tracking pixels, no Google Analytics, no Mixpanel, nothing
- **Behavioral data:** hover patterns, click patterns, scroll depth, session duration. None of it is captured.

This isn't a policy choice that could change in a future update. It's a structural decision: the code that would collect and transmit this data doesn't exist in the extension. There's no endpoint to receive it and no function to send it.

## Why this matters for a browser extension

Browser extensions occupy a uniquely sensitive position. Unlike a normal website, an extension can see the content of every page you visit across the web. That's an enormous amount of trust.

Some extensions have [abused that trust](/blog/hover-zoom-privacy-scandal). The Hover Zoom saga showed what happens when an extension with broad permissions decides to monetize user data. Users had no warning, no opt-out, and no visibility into what was being collected.

Ultra Zoom's architecture is our answer to that problem. Instead of asking you to trust a privacy policy, we built the extension so that the data simply isn't available to us. You don't have to take our word for it. The network traffic speaks for itself.

## Verify it yourself

We encourage you to audit Ultra Zoom's behavior:

1. **Network tab.** Open developer tools (F12), switch to the Network tab, and browse normally with Ultra Zoom enabled. You'll see image fetches going directly to origin servers and nothing else.
2. **Extension source.** Both Chrome and Firefox allow you to inspect installed extension source code. Look for any `fetch`, `XMLHttpRequest`, or `sendMessage` calls that point to unexpected domains.
3. **Permissions.** Check what permissions Ultra Zoom requests in your browser's extension management page. Compare them against what's needed to display images.

Privacy shouldn't require faith. It should be verifiable. That's what zero-knowledge by design means to us.

[Install Ultra Zoom](/) for Chrome or Firefox and see for yourself. Curious what went wrong with the old Hover Zoom extension? [Here's the backstory](/blog/hover-zoom-privacy-scandal).
