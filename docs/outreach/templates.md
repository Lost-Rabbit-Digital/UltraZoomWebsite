# Outreach Email Templates — Ultra Zoom

A library of email "spear" templates keyed to the blog posts on ultrazoom.app/blog. Each spear gives the pitch a specific hook that isn't "please add me to your list." The template is a starting point — always personalize the first paragraph with a specific detail from the prospect's article.

All templates:
- Plain text, no images, no tracking pixels
- 3–5 short paragraphs
- One ask, soft close
- Signed with a real name + company + product URL
- Send window: Tue–Thu, adjust timezone to author's likely location

Sign-off block (reuse across templates):
```
Best,
Boden Garman
Founder, Lost Rabbit Digital LLC
https://ultrazoom.app
```

---

## Spear index

| Spear blog post | Best for | Template id |
|---|---|---|
| Hover Zoom privacy scandal (`/blog/hover-zoom-privacy-scandal`) | Privacy blogs, security news, "open source alternatives" lists | `privacy-spear` |
| Zero-knowledge architecture (`/blog/zero-knowledge-architecture`) | Privacy blogs, "no tracking" roundups | `privacy-arch-spear` |
| Manifest V3 trap (`/blog/manifest-v3-trap`) | Dev blogs, engineering publications, extension devs | `mv3-spear` |
| Bundle budget (`/blog/bundle-budget`) | Web-perf and engineering blogs | `bundle-spear` |
| Preact over React (`/blog/preact-over-react`) | Frontend engineering blogs, Preact/React audiences | `preact-spear` |
| Native browser image zoom (`/blog/native-browser-image-zoom`) | Tech journalists, browser news, UX blogs | `native-zoom-spear` |
| Collector / auction photo zoom (`/blog/collector-auction-photo-zoom`) | Coin, stamp, card, art, auction blogs | `collector-spear` |
| Designer moodboard workflow (`/blog/designer-moodboard-hover-zoom`) | Design blogs, Dribbble/Pinterest/Behance audiences | `designer-spear` |
| Genealogy archive photo zoom (`/blog/genealogy-archive-photo-zoom`) | Genealogy blogs, family-history publications | `genealogy-spear` |
| Online shopping product photo zoom (`/blog/online-shopping-product-photo-zoom`) | Ecommerce, shopping, dropship blogs | `shopping-spear` |
| Real estate listing photo zoom (`/blog/real-estate-listing-photo-zoom`) | Real estate agent blogs, property publications | `real-estate-spear` |
| Power tips (`/blog/hover-zoom-power-tips`) | Generic productivity roundups, "extensions I use daily" | `power-tips-spear` |

---

## `listicle-generic` — default for any listicle we fit into

Use when the prospect published a "best chrome extensions" article and Ultra Zoom is a natural add. Falls back to this if no niche spear fits.

```
Subject: Quick suggestion for your [ARTICLE_TITLE] list

Hi [FIRST_NAME],

I came across your [ARTICLE_TITLE] piece on [PUBLICATION] and wanted to flag
an extension that fits right into the [SECTION] section of your list.

Ultra Zoom is a hover-to-zoom extension for Chrome and Firefox that lets you
preview full-size images just by hovering — no click, no new tab, no waiting
for a page to load and then hitting back. It works on 60+ sites including
Google Images, Amazon, Reddit, Pinterest, Twitter/X, and Instagram.

[WHY_IT_FITS — one sentence tying to their article's angle]

Free to use, no tracking, works client-side. Happy to send screenshots, a
short write-up, or whatever format makes it easy to slot in. Either way,
genuinely useful list — I've picked up a few extensions from it myself.
```

---

## `privacy-spear` — for privacy / security publications

Reference: the Hover Zoom privacy scandal and our zero-knowledge architecture.

```
Subject: The Hover Zoom story, and what we built to replace it

Hi [FIRST_NAME],

Your [ARTICLE / PUBLICATION] is one of the few places I trust for honest
takes on extension safety, so I wanted to share something I thought you
might find useful.

We just published a piece walking through what actually happened to Hover
Zoom — the spyware injection, the data-broker relationships, the ownership
trail — and how we architected Ultra Zoom (our hover-to-zoom replacement)
to make the same betrayal structurally impossible:
https://ultrazoom.app/blog/hover-zoom-privacy-scandal

The companion post on zero-knowledge architecture breaks down exactly what
stays on device and why nothing leaves it:
https://ultrazoom.app/blog/zero-knowledge-architecture

No ask beyond: if it's useful background for a future piece on extension
safety, an "open-source alternatives" roundup, or the ongoing MV3
transition, I'm happy to answer any technical questions or provide the
manifest/code walkthrough.
```

---

## `mv3-spear` — for engineering / dev publications

```
Subject: Manifest V3 post-mortem from a hover-zoom extension

Hi [FIRST_NAME],

Loved your [ARTICLE_TITLE] — especially the point about [SPECIFIC_DETAIL].

I lead engineering on Ultra Zoom, a hover-to-zoom extension we rebuilt
from the ground up for MV3. A lot of hover-zoom extensions didn't make the
transition cleanly — some broke, some resorted to remote code / dynamic
rules that defeat MV3's security model. I wrote up what we learned about
the architectural choices MV3 forces on this class of extension:
https://ultrazoom.app/blog/manifest-v3-trap

If you're writing anything on the MV3 ecosystem, extension performance, or
the privacy fallout from the migration, I'd be glad to be a source. Also
happy to share the full bundle breakdown if that would be useful:
https://ultrazoom.app/blog/bundle-budget
```

---

## `bundle-spear` — for web-perf and frontend-engineering blogs

```
Subject: What 60KB of browser extension actually does

Hi [FIRST_NAME],

I read your [ARTICLE_TITLE] and thought you might enjoy a companion data
point. We published a line-by-line breakdown of everything Ultra Zoom (a
hover-to-zoom extension) ships to the user, down to the byte, explaining
what loads when and why:
https://ultrazoom.app/blog/bundle-budget

The short version: Preact + a minimal content script, no framework
hydration on 60+ sites. Part of the reason I wrote it was a reaction to
how unexamined browser-extension bundles tend to be.

If that's useful for a future piece on real-world bundle sizing, or for
a roundup of "extensions that aren't a perf tax," happy to share any
additional numbers.
```

---

## `preact-spear` — for Preact/React/frontend publications

```
Subject: Why we picked Preact (not React) for Ultra Zoom

Hi [FIRST_NAME],

Your [ARTICLE_TITLE] was a great read. I wanted to share a small case
study I thought might land with your audience: we wrote up why we chose
Preact over React for Ultra Zoom, with the bundle numbers to justify it,
and why the migration cost away from React was close to zero:
https://ultrazoom.app/blog/preact-over-react

If a future "what framework we picked" piece would land well on
[PUBLICATION], I'm happy to go into more depth on the decision or share
the build pipeline.
```

---

## `native-zoom-spear` — for tech journalists / browser news

```
Subject: Why native browser image zoom is still terrible in 2026

Hi [FIRST_NAME],

Long-time reader — your [ARTICLE_TITLE] was a useful piece.

I run a hover-to-zoom extension (Ultra Zoom) and finally wrote up
something I've been ranting about privately for years: every major
browser has had the building blocks for native image zoom since the
early 2000s, and none of them stitched the pieces together. Here's the
post:
https://ultrazoom.app/blog/native-browser-image-zoom

If you ever cover browser UX, extension stories, or the MV3 transition,
happy to be a source. I'm also available for comment on the Hover Zoom
privacy scandal, which is still surprisingly under-reported.
```

---

## `collector-spear` — for coin, stamp, card, auction, art blogs

```
Subject: A hover-zoom tool for inspecting [NICHE] listing photos

Hi [FIRST_NAME],

I'm a [collector / fan] of [PUBLICATION / NICHE] — your recent piece on
[ARTICLE_TITLE] was a useful read.

I wanted to share a tool that might resonate with your readers. We built
Ultra Zoom, a hover-to-zoom browser extension that pops the full-resolution
image of any listing thumbnail on hover — on eBay, Heritage Auctions,
Catawiki, WorthPoint, and 60+ other sites. For collectors inspecting
condition, grading, and detail before bidding, it removes a lot of
click-open-close friction.

We wrote up the specific collector workflow here in case it's useful:
https://ultrazoom.app/blog/collector-auction-photo-zoom

No paid placement, just thought it might fit the audience. Happy to
provide screenshots or a short write-up if you'd like to mention it in
a "tools for collectors" roundup or a buyer's guide.
```

---

## `designer-spear` — for design blogs, Dribbble/Pinterest/Behance audiences

```
Subject: Hover-to-zoom for faster moodboarding

Hi [FIRST_NAME],

I read [ARTICLE_TITLE] on [PUBLICATION] and wanted to share a tool
built specifically for the moodboarding + inspiration-gallery workflow
you describe.

Ultra Zoom is a hover-to-zoom extension for Chrome and Firefox. Hover
any thumbnail on Pinterest, Dribbble, Behance, Are.na, or 60+ other
sites and the full-resolution image pops instantly — no click, no new
tab. We wrote up how working designers use it here:
https://ultrazoom.app/blog/designer-moodboard-hover-zoom

If you do a "tools for designers" or "chrome extensions for creatives"
piece, I'd love to be considered. Happy to send a short demo video or
screenshots.
```

---

## `genealogy-spear` — for genealogy / family-history blogs

```
Subject: A hover-zoom tool for Ancestry, FamilySearch, and newspaper archives

Hi [FIRST_NAME],

I've been reading [PUBLICATION] for [CONTEXT]. Your piece on
[ARTICLE_TITLE] was exactly the kind of practical advice that's hard to
find.

I wanted to share a free tool in case it's useful for your readers. Ultra
Zoom is a hover-to-zoom browser extension that magnifies any image or
scanned document on hover — we spent time tuning it for the genealogy
workflow specifically (cursive census pages, faded portraits, newspaper
clippings, immigration manifests). Writeup with the Ancestry and
FamilySearch specifics:
https://ultrazoom.app/blog/genealogy-archive-photo-zoom

If you have a "tools" roundup or a tips post where it'd fit, I'd be
honored to be considered. Either way, thanks for the work you do —
the genealogy blog ecosystem is one of the best on the internet.
```

---

## `shopping-spear` — for ecommerce / shopping / dropship blogs

```
Subject: Hover-to-zoom for product photo inspection

Hi [FIRST_NAME],

Your [ARTICLE_TITLE] post was really useful — especially the
[SPECIFIC_DETAIL].

I wanted to share a free tool that fits the product-photo-inspection
angle. Ultra Zoom is a hover-to-zoom extension for Chrome and Firefox
that pops full-resolution product images on Amazon, eBay, AliExpress,
Etsy, Shopify stores, and 60+ other sites. For shoppers, dropshippers,
and ecommerce operators doing supplier or competitor research, it removes
the "click every listing to inspect" step.

Full writeup with the Amazon / Etsy / eBay workflow:
https://ultrazoom.app/blog/online-shopping-product-photo-zoom

If you have a "tools for [YOUR_AUDIENCE]" or extension roundup coming
up, I'd love to be considered. Happy to provide any format you need.
```

---

## `real-estate-spear` — for real estate / property / agent blogs

```
Subject: A hover-zoom trick for inspecting Zillow and Redfin listings

Hi [FIRST_NAME],

Long-time reader of [PUBLICATION]. Your [ARTICLE_TITLE] piece was
especially useful — [SPECIFIC_DETAIL].

I wanted to share a free tool built for agents and buyers who spend a
lot of time in listing photos. Ultra Zoom is a hover-to-zoom browser
extension that pops the full-resolution version of any listing thumbnail
on hover. On Zillow, Redfin, Realtor.com, and 60+ other sites, it
eliminates the click-through-each-photo step and makes it much faster
to spot red flags the photographer tried to hide.

Writeup with the specific checklist real estate agents use:
https://ultrazoom.app/blog/real-estate-listing-photo-zoom

If you run a "tools for agents" roundup or a buyer's guide, I'd love to
be considered.
```

---

## `power-tips-spear` — for generic productivity / "extensions I use daily" articles

Tighter alternative to `listicle-generic`. Use when the author is clearly an extension power user.

```
Subject: Three hover-zoom shortcuts I think you'll enjoy

Hi [FIRST_NAME],

Your [ARTICLE_TITLE] was my kind of post — especially the
[SPECIFIC_DETAIL] part.

Quick tip you might enjoy: I run a hover-to-zoom extension called Ultra
Zoom, and the power-user shortcuts (scroll-to-zoom further, arrow-key
gallery nav, per-site toggles) make it unexpectedly fast once they're
habits. Short writeup:
https://ultrazoom.app/blog/hover-zoom-power-tips

Works on Chrome and Firefox across 60+ sites. If a future "extensions I
use daily" piece would land on [PUBLICATION], I'd love to be considered.
No hard pitch — the post is a fun read either way.
```

---

## Follow-up (7 days after initial send, no reply)

```
Subject: Re: [ORIGINAL_SUBJECT]

Hi [FIRST_NAME],

Bumping this in case it slipped past — totally fine if it's not a fit.
If it'd help, I can send a 2-minute demo video or a short write-up
formatted to match your list style. Otherwise, no need to reply.

Best,
Boden
```

---

## Final personalization checklist (before every send)

- [ ] First paragraph contains a specific detail from their article (not generic praise)
- [ ] Subject line is under 60 characters and reads like a real human, not marketing
- [ ] Body has one ask, soft close, no bulleted feature list
- [ ] Relevant blog spear link is present and fits the pub's beat
- [ ] Name, role, and context match the spear (e.g., `privacy-spear` should sound like our founder, not marketing)
- [ ] Sign-off has real name, company, one URL (no email-signature image)
- [ ] Send window matches author's timezone
