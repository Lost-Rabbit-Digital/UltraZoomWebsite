# Outreach Research — Claude Cowork Prompt

A prompt tuned for **Claude Cowork** (live browser-shared session) rather than a headless Code or Routines run. Cowork can actually load Google / Bing result pages, click through to article pages, see contact / about pages, and pull live bylines — so it dodges the biggest failure mode of the other prompts (stale or hallucinated contact info).

Pair with:
- `docs/outreach/dorks.md` — search operators
- `docs/outreach/templates.md` — email spear library
- `docs/outreach/leads.json` — dedupe against the running list
- `docs/outreach/iteration-prompt.md` — non-browser variants

---

## When to use this vs. the other prompts

| Prompt | Best when |
|---|---|
| `cowork-prompt.md` (this file) | You want fresh, verified contacts and you're watching. Live search + pair-review. |
| `iteration-prompt.md` interactive | You want to run a batch while watching, no live browser required. |
| `iteration-prompt.md` routine | Scheduled / unattended batches. Lower accuracy on contacts, higher volume. |

Rule of thumb: use Cowork for the first batches each month (high-quality seed leads), then let the Routine top up between human passes.

---

## Cowork prompt

Paste into a new Claude Cowork session with the target repo open and a fresh browser tab ready. The session should have the Ultra Zoom repo cloned locally (or file access via Desktop / web with project sync) and read access to `docs/outreach/*`.

```
We're pair-researching the next batch of outreach prospects for Ultra Zoom
(a hover-to-zoom browser extension for Chrome and Firefox — ultrazoom.app).
You'll drive the browser, I'll steer. Goal: end this session with 10–20
verified, ready-to-email leads added to docs/outreach/leads.json and a
matching draft file per lead in docs/outreach/drafts/.

### Read first, then pause and summarize what you found
1. docs/outreach/leads.json  (existing leads — dedupe source of truth)
2. docs/outreach/dorks.md     (search-operator library)
3. docs/outreach/templates.md (spear library)
4. docs/outreach/iteration-prompt.md (priority lanes, fields to collect)

Before any browser work, report back:
 - current lead count / 300 target
 - which blog-spear categories are thinnest in leads.json
 - three candidate dork queries you'd like to run first (prefer listicle
   dorks; our primary lane is Chrome/Firefox extension roundups)
 - any existing publications you'd recommend we NOT re-contact
Wait for my green light before running the searches.

### Research loop (repeat per lead)

A. Run one dork query in Google (or Bing if Google captcha-gates).
   Open the top 10 organic results in new tabs. Skip ads, skip the
   dedupe set from leads.json, skip known content farms
   (quickanswer.io, listify, AI-generated spam sites).

B. For each candidate tab, open it and confirm:
   - article is live (no 404 / paywall / cookie wall that hides body)
   - article is a listicle / roundup / niche publication we want
   - article was published within the last 24 months
   - article has a named author (not just "admin" or empty byline)
   - article does not already include Ultra Zoom
   If any check fails, close the tab and move on.

C. Extract into a lead row:
   - publication (company / site name)
   - article_title and article_url
   - author full name and role
   - publication domain
   - publish or last-updated date

D. Find contact info. In order:
   1. Author byline link (click it; author page often lists email or socials)
   2. /about, /contact, /team, /editorial pages on the publication
   3. Twitter/X profile (the bio sometimes has "email me at …")
   4. LinkedIn profile (click through from the author byline)
   5. Pattern inference only as last resort, and only if we can see at
      least one example email on the domain confirming the pattern
      (e.g., the /team page shows "jane@pub.com" so firstname@pub.com
      is a safe inference).
   Record:
     contact_email
     contact_method (email | form | linkedin | twitter)
     contact_confidence (verified | pattern_inferred | unverified)
     contact_notes (where you found it, e.g. "about page lists tips@…")

E. Pick the blog_spear from docs/outreach/templates.md that fits the
   article's beat. Default: listicle-generic. For niche pubs pick
   privacy / engineering / collector / designer / genealogy / shopping /
   real-estate / power-tips spear as appropriate.

F. Show me the proposed row as JSON and the chosen spear. I'll confirm,
   edit, or reject. No writes to the repo until I confirm.

G. On my confirm, write:
   - the new entry into docs/outreach/leads.json (append, bump id,
     preserve array order and formatting)
   - a new draft file docs/outreach/drafts/<id>-<slug>.md built from the
     chosen spear in templates.md, personalized paragraph 1 with a
     specific detail you saw in the article
   Sign-off block:
     Best,
     Boden McHale
     Founder, Lost Rabbit Digital LLC
     https://ultrazoom.app

H. Tell me the running total and move to the next tab.

### Cowork-specific safety
- If Google shows a captcha, pause and ask me to solve it — don't try to
  bypass.
- If a site blocks scraping (Cloudflare, hCaptcha), describe what you see
  and I'll decide whether to skip or help.
- If a cookie banner hides the article, accept the minimum / essential
  option or tell me and I'll dismiss it myself.
- If you find a contact email but the pattern looks off (e.g., info@
  for a personal author), down-rank confidence to pattern_inferred and
  add a note.
- NEVER fabricate an email. "unverified" + status: research_pending is
  correct when you can't confirm a real contact.

### Batch rules
- Target 10–20 leads this session. Stop when we hit 20 or when search
  results start repeating.
- Commit in small batches: every 5 leads, show me the diff for
  leads.json and offer to git add + commit with message
  "outreach: add N cowork-verified prospects (<date>)".
- Do NOT push without asking.
- Do NOT open a PR without asking.

### Closing
At the end, print:
 - leads added this session (id range, publications, spear distribution)
 - new total / 300
 - categories that are still thin per docs/outreach/dorks.md
 - three suggested queries for next session
```

---

## User-side tips during a Cowork session

- Keep `leads.json` open in a second window so you can eyeball the diff.
- If a prospect looks hot, ask Claude to also scan their recent articles for a more specific angle — a personal, current-article detail in paragraph 1 doubles reply rates vs. a generic reference.
- If Cowork struggles with a publication's cookie / captcha wall, use your own browser tab, paste the article text into chat, and Claude can continue from there without leaving the session.
- At the end of each session, run the `schedule-outreach-drafts` routine (or the interactive variant in `gmail-drafts-prompt.md`) to push the new draft-ready leads into Gmail.

---

## Handoff cues between Cowork, interactive, and routine runs

The three research modes write to the same `leads.json`. Convention:

- Cowork sessions add leads in **small verified batches** (10–20), typically tagged `contact_confidence: "verified"`.
- Interactive iteration adds **medium batches** (20–40), mostly `verified` or `pattern_inferred`.
- Routine runs add **bulk batches** (up to 40) with a higher share of `pattern_inferred` / `research_pending`.

The Gmail scheduling routine only picks up `status: draft_ready`, so `research_pending` leads from routine runs won't get into Gmail until a human (or a future Cowork session) verifies the contact and flips the status.
