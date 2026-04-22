# Contact-Form Outreach Templates — Ultra Zoom

Short copy-paste messages tuned for **contact forms** (not email). Forms reward:
- Brevity (many cap at ~1000 chars)
- A single, low-friction ask
- Zero formatting that could break on submit (no markdown, no bullets, no links besides one)
- One URL max — extra links trigger spam filters on Formspree / WPForms / HubSpot

Pair each message with the `template` column in `docs/outreach/leads-contact-form.csv`.
Merge fields are UPPER_SNAKE — fill before submitting.

Sign-off (reuse across all templates):
```
— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

---

## `form-listicle` — default for any "best X extensions" roundup

```
Hi there,

I came across your piece "ARTICLE_TITLE" while researching browser extension
roundups and wanted to flag one that fits the SECTION section: Ultra Zoom, a
hover-to-zoom extension for Chrome and Firefox.

It works on 60+ sites (Google Images, Amazon, Reddit, Pinterest, eBay, Zillow,
Ancestry, etc.) — hover any thumbnail, see the full-size image, no click, no
new tab. Free to use, no tracking, client-side only.

If it's useful, I'd be grateful for a mention. Happy to send screenshots or a
GIF, or answer anything you'd want to cover.

— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

**When to use:** "best chrome extensions", "must-have browser extensions", "extensions I use daily" — any generic listicle.
**Merge:** `ARTICLE_TITLE`, `SECTION` (e.g. "productivity", "image tools", "for designers").

---

## `form-photo-design` — photographers, designers, moodboard workflows

```
Hi PUBLICATION team,

Your "ARTICLE_TITLE" post popped up while I was researching tools for
image-heavy workflows. I wanted to share Ultra Zoom in case it's worth a
mention in a future update.

It's a hover-to-zoom browser extension that previews full-size images on
Pinterest, Behance, Dribbble, Google Images, and 50+ other sites without
opening a new tab. Makes moodboard browsing and reference hunting a lot
faster. Free, no tracking, Chrome + Firefox.

Happy to send a GIF or chat about the design side if it's useful.

— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

**Merge:** `PUBLICATION`, `ARTICLE_TITLE`.

---

## `form-shopping` — eBay, Amazon, dropshipping, reselling, auction

```
Hi,

I read your "ARTICLE_TITLE" piece — useful for anyone who spends time
sourcing on eBay / Amazon / auction sites. I thought I'd flag a tool that
fits the workflow: Ultra Zoom.

It's a hover-to-zoom browser extension. On eBay, Amazon, and dozens of other
shopping sites, you just hover a listing thumbnail and see the full-resolution
photo — no click-through, no back-button dance. Really handy for inspecting
condition on used items. Free, Chrome + Firefox.

If it's a fit, I'd love a mention in the article or a future update. Can send
a GIF on request.

— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

**Merge:** `ARTICLE_TITLE`.

---

## `form-genealogy` — ancestry / familysearch / archive researchers

```
Hi there,

Found your "ARTICLE_TITLE" while looking for genealogy research tools worth
sharing with our users. Wanted to share one back: Ultra Zoom.

It's a free hover-to-zoom browser extension that works on Ancestry.com,
FamilySearch, Findagrave, and 50+ other sites — hover a scanned document or
photo thumbnail, see the full-resolution image immediately, no modal, no
re-loading. Saves a lot of clicks when reviewing census pages or old photos.
Chrome + Firefox, no tracking.

If it's useful to your readers, a mention would mean a lot. Happy to send
example workflows.

— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

**Merge:** `ARTICLE_TITLE`.

---

## `form-real-estate` — zillow, redfin, homebuying tools

```
Hi,

Came across "ARTICLE_TITLE" and wanted to flag a browser tool that fits
well with house-hunting research: Ultra Zoom.

It's a free hover-to-zoom extension for Chrome and Firefox. On Zillow,
Redfin, Realtor.com, and 50+ other sites you hover any listing photo and
see the full-size image — no lightbox, no click through all 40 photos
individually. Much faster for filtering homes at the shortlist stage.

If it's worth a mention, I'd be grateful. Can share a GIF of the Zillow
workflow if useful.

— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

**Merge:** `ARTICLE_TITLE`.

---

## `form-privacy` — privacy / security blogs

```
Hi,

Your "ARTICLE_TITLE" article came up while I was looking for privacy-minded
publications. I wanted to share a project that fits the angle: Ultra Zoom.

It's a hover-to-zoom browser extension, which is a category that has a long
and ugly history with privacy (the original Hover Zoom was caught selling
browsing data in 2014). Ultra Zoom is the counter-argument: zero telemetry,
no analytics, no history collection, no third-party servers — everything
runs in-browser. Chrome and Firefox, free with optional Pro.

If you cover the space, I'd love your take. Happy to walk through the
zero-knowledge architecture.

— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

**Merge:** `ARTICLE_TITLE`.

---

## `form-generic` — fallback when no spear fits

```
Hi,

Found you through "ARTICLE_TITLE" and wanted to briefly introduce a project
that might be a fit for your audience: Ultra Zoom, a hover-to-zoom browser
extension for Chrome and Firefox.

It works on 60+ websites — hover any image thumbnail, see the full-size
image instantly, no click, no new tab. Free, privacy-first (no tracking),
built by a small indie studio.

If it's something you'd consider covering or mentioning, I'd love that. Can
send screenshots, a GIF, or anything else useful.

— Boden McHale, Lost Rabbit Digital LLC
https://ultrazoom.app
```

**Merge:** `ARTICLE_TITLE`.

---

## Submission hygiene

- **One URL max.** Forms with 2+ links get flagged as spam on most backends.
- **No markdown** — some forms render `**bold**` literally.
- **Pick the author's first name** if the form has a "name" field that's clearly for attention-routing; otherwise "Hi there" is fine.
- **Subject lines:** if the form has one, use `Quick note on your "ARTICLE_TITLE" post` — avoid "partnership", "collaboration", "promotion".
- **Don't mention Pro** in the first touch. The free tier is the hook.
- **Keep the sign-off identical** across templates so replies are easy to spot in inbox.

## Status values (used in `leads-contact-form.csv`)

| Value | Meaning |
|---|---|
| `new` | Just discovered by `find-leads.mjs`. Needs triage. |
| `kill` | Not a fit. Leave in CSV for dedupe; do not submit. |
| `triaged` | Reviewed, template picked, contact URL confirmed. Ready to submit. |
| `submitted` | Message posted via form. Set `message_sent` to today's date. |
| `replied_positive` | Got a reply, willing to list / update. |
| `replied_negative` | Got a decline. |
| `linked` | Saw Ultra Zoom added to the article. |
| `no_reply` | 30+ days since submit, nothing heard. |
| `bounced` | Form failed (captcha, 500, email bounced back). |
