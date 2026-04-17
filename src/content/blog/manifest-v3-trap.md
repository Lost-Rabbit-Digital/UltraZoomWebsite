---
title: "The Manifest V3 trap: why most hover-zoom extensions had to choose between breaking and spying"
description: "Manifest V3 reshaped what browser extensions can do. For hover-zoom tools, the migration created a fork in the road — and a lot of extensions took the wrong path."
date: 2026-04-15
category: "Engineering"
---

When Google announced Manifest V3, the pitch was privacy and performance. The reality, for extension developers, was a migration that forced uncomfortable architectural decisions. Hover-zoom extensions were hit particularly hard, and a surprising number of them came out the other side worse than they went in.

Here's what actually changed, what it meant for image-zoom tools, and how we navigated it while building Ultra Zoom.

## What Manifest V3 actually took away

Three changes matter for a hover-zoom extension:

**Persistent background pages are gone.** In MV2, an extension could run a long-lived background page that held state, cached fetches, and intercepted network traffic. MV3 replaces that with service workers that the browser kills after ~30 seconds of inactivity. Any in-memory state evaporates between events.

**Remote code execution is banned.** MV2 extensions routinely loaded JavaScript from a remote server at runtime. That's now a policy violation and a technical one — `eval`, remote `<script>` tags, and fetched-then-executed code will get an extension pulled from the Chrome Web Store.

**`webRequest` is neutered.** The blocking `webRequest` API — the one that let extensions inspect, modify, or cancel network requests on the fly — is read-only for most developers. You're expected to use `declarativeNetRequest`, which takes static rule files and runs them in the browser's native networking stack.

Each of these sounds like a reasonable hardening. Together, they broke a generation of hover-zoom extensions.

## Why hover-zoom extensions struggled

A typical pre-MV3 hover-zoom tool worked like this: the background page kept a registry of site-specific rules, intercepted thumbnail requests to figure out the full-size URL, and fetched images through its own network layer to bypass hotlink protection and CORS. When MV3 arrived, every one of those techniques needed a rewrite.

The shortcuts some extensions took:

- **Expanding host permissions to "all URLs"** to regain access they used to have narrowly. This is the opposite of what MV3 was supposed to achieve — broader access, not less.
- **Shipping a remote configuration server** that pushes JSON rules to every user on every launch. Technically compliant, practically a surveillance channel: every config fetch leaks your user agent, IP, and extension version to the developer's server.
- **Moving zoom logic into content scripts with unrestricted page access**, which means the extension now runs on every site you visit, not just the ones that need zoom support.
- **Bundling analytics SDKs** to "measure migration impact," which conveniently stuck around long after the migration ended.

Each of these is a form of the Hover Zoom failure mode we wrote about in [the privacy scandal post](/blog/hover-zoom-privacy-scandal) — a structural decision that makes data exfiltration easy or inevitable.

## How Ultra Zoom navigated it

We rebuilt Ultra Zoom against MV3 as a deliberate constraint, not a compliance checkbox:

**Static rules, shipped in the package.** The site-specific logic that tells Ultra Zoom how to find a full-resolution image on Reddit, Etsy, or eBay lives in a JSON file inside the extension bundle. It's reviewed when we submit the extension and it doesn't change until you update. No remote config, no runtime fetches for rules.

**No background network interception.** Ultra Zoom doesn't use `webRequest` or `declarativeNetRequest` to inspect your traffic. Image fetches are initiated by content scripts, using the same CORS behavior any other page would see. If a site blocks hotlinking, Ultra Zoom respects that — we don't route around it with a proxy.

**Service worker holds no state worth stealing.** Our service worker handles two things: license validation at activation, and routing keyboard shortcut events. It doesn't cache URLs, doesn't maintain a history buffer, doesn't ping home. If the browser kills it after 30 seconds, nothing is lost. It's also small — about 2.6 KB gzipped — because it does small things. We [break down the rest of the bundle](/blog/bundle-budget) in a separate post.

**Permissions scoped to supported sites.** Ultra Zoom requests host access only for the sites listed on the [Help page](/help). It does not ask for "all websites." If we want to add a new site, we ship an update — and you see the new permission in your browser's update prompt before it takes effect.

## The lesson

Manifest V3 didn't force extensions to spy on users. It removed a few convenient patterns and asked developers to adapt. The extensions that leaned on the worst workarounds — broad permissions, remote config, bundled analytics — chose that path. They weren't cornered into it.

If you're evaluating a hover-zoom extension, the MV3 migration is a useful lens. Look at what permissions the current version requests compared to two years ago. Look at whether it fetches configuration at runtime. Look at whether the update notes mention analytics or telemetry being added "for reliability." The path an extension took through MV3 tells you what the developer prioritized.

Ultra Zoom took the narrow path on purpose. [Install it](/) and audit the network traffic yourself.
