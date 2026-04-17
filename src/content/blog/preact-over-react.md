---
title: "Why we picked Preact over React for a browser extension"
description: "React is a fine default for web apps. For a browser extension where every kilobyte ships to every user, Preact is a better fit — and the migration cost is close to zero."
date: 2026-04-17
category: "Engineering"
---

Ultra Zoom's popup and options pages are built with Preact, not React. We didn't switch from one to the other; we picked Preact on day one and have never regretted it. This post is the reasoning, with the actual bundle numbers attached.

## The numbers that decided it

Preact 10 is **~11 KB minified** for the core library. React 18 plus ReactDOM is **~140 KB minified**. That gap doesn't go away with tree-shaking, because the overlap in what's actually imported is small — React's runtime includes things Preact simply doesn't have (Concurrent Mode scheduling, a richer reconciler, the legacy event system).

For Ultra Zoom's popup, the shared Preact runtime plus hooks is about **10 KB gzipped**. The same UI on React would be closer to **~45 KB gzipped** before we wrote a line of our own code. That's not a micro-optimization — it's a quarter of our entire popup budget.

For a marketing site, 35 KB of extra JavaScript is forgettable. For an extension review queue, it's 35 KB of code a reviewer has to account for. For a user on a slow device, it's 35 KB the browser parses before the popup is interactive. The framing matters.

## The API compatibility argument

The usual concern about Preact is "what if we hit a React feature it doesn't support." In practice, for an extension UI, there are three features this could mean:

**Hooks.** Preact 10 has full hooks support — `useState`, `useEffect`, `useMemo`, `useContext`, `useRef`, `useReducer`, `useCallback`. Our code reads identically to React hooks code.

**JSX.** We use JSX via `@preact/preset-vite`. Our components look like React components. A developer who knows React can read our codebase immediately; most of them don't notice it's Preact until they check the imports.

**Ecosystem libraries.** This is where the compatibility shim matters. `preact/compat` aliases `react` and `react-dom` to Preact, so most React ecosystem libraries work. We haven't needed it — our UI is small enough that we write our own components — but it's there as an escape hatch.

The features we don't get with Preact: Concurrent Mode, Suspense-for-data-fetching, Server Components. None of these are relevant for a browser extension popup. We're not suspending on data fetches; our entire state is a synchronous read from `chrome.storage.local`.

## What Preact doesn't help with

Preact is a UI library, and it only helps on surfaces that render UI. Ultra Zoom has four surfaces:

- **Popup** — Preact. ✓
- **Options page** — Preact. ✓
- **Welcome page** — Preact. ✓
- **Content script** — plain TypeScript over DOM APIs. Preact is not loaded here.
- **Service worker** — plain TypeScript. No DOM, nothing to render, Preact is irrelevant.

The content script is the one that would have been a disaster with React. It runs on every page where the extension is active. Shipping a reactive rendering framework inside a content script that injects into Gmail, Amazon, and every news site would blow up the budget — not just ours, but the host page's. So we don't. Content script UI (the zoom overlay) is imperative DOM code: `document.createElement`, style manipulation, event listeners. It's ~58 KB minified, ~18 KB gzipped, and that includes all the hover detection logic.

The popup and options pages are where reactivity earns its keep. Toggling a setting in the popup needs to reflect in the UI immediately, update `chrome.storage.local`, and propagate to the content script via a message. Writing that against raw DOM is possible but painful — you end up reinventing a small reactive system. Preact is that reactive system, already written, audited, and ~10 KB gzipped. That's a fair price.

## The specific things that nudged us

Four concrete moments where Preact paid off:

**Chrome Web Store review.** Reviewers read the code that ships. A smaller, more conventional runtime means less unfamiliar code for them to sign off on. React's event delegation and synthetic event system add real surface area to explain. Preact's internals are small enough to skim.

**Firefox review.** Same logic, different reviewers. The AMO team has flagged us zero times for dependency concerns. We've read review decisions on other extensions where bundled framework size was called out as a review-slowing factor.

**First paint on toolbar click.** On cold popup open, the gap between clicking the toolbar and seeing rendered content is dominated by JS parse time. Moving from ~45 KB gzipped framework code to ~10 KB measurably shortens that window. We haven't published microbenchmarks because they're fiddly, but the perceptual difference on a mid-range laptop is real.

**Contributor onboarding.** React developers open our codebase, see JSX and hooks, and write code. The `@preact/preset-vite` import line is the only adjustment. We've never had a contributor confused by Preact-specific behavior.

## Where we'd reconsider

Preact is the right call for Ultra Zoom. It would not automatically be the right call for a different extension.

**If the UI was substantially bigger** — say, a full tab-replacement extension with dozens of views, heavy form libraries, and a component library — the React ecosystem's depth starts to matter. You'd be pulling `preact/compat` in for most of it, and at that point the size advantage narrows.

**If we needed Suspense or Server Components** — not on the roadmap, not a thing inside an extension, but worth flagging.

**If the team was reaching for React-specific tooling** — React DevTools works with Preact via a bridge, but it's not as smooth. A team that lives in React DevTools every day would feel the difference.

None of these apply to us. Ultra Zoom's popup is a few dozen components, our state is `chrome.storage.local`, and our team is four people who read MDN more than they read React docs.

## The meta-point

"Use React" is the industry default. For most web apps, it's a reasonable default. For a browser extension, the constraints are different: code size is a visible user cost, the review queue treats bundle size as signal, and the framework runtime is something auditors have to account for.

Preact makes the tradeoff explicit. You trade a little ecosystem depth for ~35 KB gzipped and a much smaller runtime surface. For an extension, that trade is almost always worth it. It's worth it for us.

If you're building an extension and haven't looked at Preact, look. The migration is trivial, the API is familiar, and the bundle-size win is real. You can keep writing React-shaped code and ship a third of the framework weight.
