---
title: "We rewrote Ultra Zoom in vanilla JS and deleted 400KB of dependencies"
description: "What we gained, what we gave up, and why a framework was the wrong choice for a browser extension that ships on every page load."
date: 2026-04-17
category: "Engineering"
---

A few releases back, Ultra Zoom's popup and options pages were built on a small JavaScript framework. It was fine. The dev experience was good, state management was tidy, and onboarding a new contributor took an afternoon.

It was also the wrong choice. This post explains why we ripped it out, what the rewrite actually looked like, and what we'd do differently if we were starting today.

## The starting point

Before the rewrite, Ultra Zoom shipped with:

- A framework runtime, JSX compiler output, and hydration layer in both the popup and options pages
- A state management library for per-site preferences
- A UI component library that gave us toggles, sliders, and modal dialogs
- Build-time CSS-in-JS that generated a style manifest
- Around **23 npm dependencies** (direct), resolving to **180+ transitive packages**
- A **~430KB** popup bundle after tree-shaking and minification, gzipped to ~120KB

For a web app, that's unremarkable. For a browser extension that loads on every toolbar click and needs to be audited by Chrome Web Store and Firefox Add-ons review teams, it's a lot.

## Why a framework was wrong for us

Three reasons it stopped making sense:

**Review surface.** The Chrome Web Store and Firefox Add-ons teams review the code that ships in the package. A framework runtime is code we didn't write, bundled inside code we did. When a reviewer asks "what does this function do," "minified framework internals" is an annoying answer. Shipping readable, hand-written code shortens review cycles and makes our claims about [zero-knowledge architecture](/blog/zero-knowledge-architecture) easier to verify.

**Supply chain.** Every transitive dependency is a package that could be compromised, abandoned, or sold. The [Hover Zoom scandal](/blog/hover-zoom-privacy-scandal) is what happens when a trusted piece of code changes hands. A framework pulls in hundreds of packages, maintained by hundreds of people, any of which could ship a malicious update. For an extension that sees the content of every page, that's not an acceptable risk profile.

**Performance math.** The popup renders maybe six toggles, a search box, and a list of supported sites. We were shipping a reactive rendering engine to manage six toggles. On a cold toolbar click, the framework's hydration step added 40–80ms of blocking JavaScript before the UI was interactive. For a click-and-done interaction, that's noticeable.

## The rewrite

We replaced the framework with three things:

**Plain DOM APIs.** `document.createElement`, `addEventListener`, `element.textContent`. The popup is now about 200 lines of JavaScript that reads preferences from `chrome.storage.local`, builds the DOM once, and wires up event listeners. There's no virtual DOM, no reconciliation, no component lifecycle.

**Web Components for the one reusable widget.** Our site-toggle row appears in both the popup and options page. It's a custom element (`<uz-site-toggle>`) that takes attributes, renders its internal DOM, and dispatches a `change` event. Native browser APIs, no build step, no runtime dependency.

**CSS custom properties for theming.** The same design tokens from `styles.css` on the marketing site, dropped directly into the extension. Dark mode is a single `[data-theme="dark"]` selector. No CSS-in-JS, no style manifest, no runtime style injection.

## The numbers

After the rewrite:

- **23 direct dependencies → 2** (both build-time: Astro for the docs site, esbuild for the extension bundle)
- **180+ transitive packages → 14**
- **430KB popup bundle → 38KB**
- **120KB gzipped → 11KB**
- **Cold toolbar click to interactive: 40–80ms → under 10ms**

The options page dropped from 280KB to 52KB. The content script — which runs on every page where Ultra Zoom is active — went from 94KB to 31KB.

## What we gave up

Honestly, less than we expected:

- **Hot module reload is gone.** The dev loop is now "save, reload the extension, click the toolbar." It's fine. The popup is small enough that a full reload is under a second.
- **TypeScript inference across components is weaker.** We kept TypeScript for type-checking, but without a framework's component model, the types don't flow through JSX the way they used to. We write slightly more explicit type annotations. Not a big deal.
- **Onboarding is different.** A new contributor who knows React doesn't have transferable patterns to lean on. They do have MDN, which is arguably a feature.

We did not give up: accessibility (actually improved — we hand-write ARIA and nobody is abstracting it away), testing (Playwright doesn't care what rendered the DOM), or state persistence (`chrome.storage.local` is the only store we need).

## Would we do it again?

Yes. The rewrite took two developers about three weeks. It paid for itself in the next Chrome Web Store review cycle, which finished in four days instead of three weeks. It paid for itself again in the next security audit, where the auditors finished early because there was less code to look at.

For a browser extension specifically — where you control the runtime, the surface area is small, and every kilobyte ships to every user — frameworks have a weaker case than people assume. We're not arguing against frameworks in general. We are arguing that "use the framework" is a default, not a decision, and that defaults are worth questioning when the constraints don't match the defaults' assumptions.

Ultra Zoom is the size it is because we kept asking what we could remove. [Install it](/) and watch the toolbar click land instantly. That's what 38KB feels like.
