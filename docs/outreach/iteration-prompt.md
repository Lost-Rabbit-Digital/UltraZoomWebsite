# Listicle Outreach — Iteration Prompt

Prompts for running the next batch of outreach research. Three versions:

1. **Interactive** — paste into a new Claude Code session you're watching
2. **Routines-compatible** — self-contained, non-interactive, runs as a Claude Routine and opens a PR
3. **Cowork** (live-browser pair session) — see `cowork-prompt.md`. Best for high-quality seed leads with verified contacts.

Goal: reach **300 verified prospects** in `docs/outreach/leads.json` so we can send 10 personalized emails per day for a full month. Primary lane: **Chrome / Firefox extension listicle articles.** Secondary lanes: niche / use-case publications (collectors, designers, genealogists, real estate agents, privacy, engineering).

Running tally is in `docs/outreach/leads.json`. Companion files:
- `docs/outreach/dorks.md` — search-operator reference
- `docs/outreach/templates.md` — email spear library
- `docs/outreach/gmail-drafts-prompt.md` — Gmail MCP workflow for scheduling drafts
- `docs/outreach/drafts/` — per-lead draft markdown files
- `docs/outreach/scheduled-log.json` — created after first Gmail sync

---

## Interactive prompt (paste into a new session)

```
I need you to find the NEXT batch of 20–40 outreach prospects for Ultra Zoom,
avoiding duplicates from previous batches.

### Context
- Product: Ultra Zoom — hover-to-zoom browser extension for Chrome and Firefox
  that works on 60+ websites (Google Images, Amazon, Reddit, Pinterest,
  Twitter/X, Instagram, Etsy, eBay, Zillow, Ancestry, etc.). Free with optional
  Pro features.
- Publisher: Lost Rabbit Digital LLC
- Website: https://ultrazoom.app
- Blog: https://ultrazoom.app/blog (use blog posts as email "spears" — see
  docs/outreach/templates.md for the spear library)
- Goal: reach 300 total verified prospects in leads.json so we can send
  10/day for a month.

### Priority lanes (in order)
1. Chrome and Firefox extension LISTICLE articles — highest fit, highest
   response rate. Default priority.
2. Niche blogs we can spear with a use-case blog post:
   - Privacy / security → hover-zoom-privacy-scandal, zero-knowledge-architecture
   - Engineering / web-perf → manifest-v3-trap, bundle-budget, preact-over-react,
     native-browser-image-zoom
   - Collectors / auctions → collector-auction-photo-zoom
   - Designers → designer-moodboard-hover-zoom
   - Genealogists → genealogy-archive-photo-zoom
   - Online shopping / ecommerce → online-shopping-product-photo-zoom
   - Real estate → real-estate-listing-photo-zoom
3. Power-user / "extensions I use daily" personal blogs → power-tips

### Already contacted (do NOT include)
Read docs/outreach/leads.json for the full list. Skip any publication, author,
or URL that already appears. Also skip any URL listed in
docs/outreach/scheduled-log.json (if present).

### Search strategy
Use the dork library in docs/outreach/dorks.md. For each iteration, pick a
mix:
- 60% listicle dorks from section 1–3 of dorks.md
- 40% niche dorks from sections 4–11 (rotate which niches each iteration)
- If a niche has < 5 leads in leads.json, bias toward it ("Prospect categories
  we're still thin on" section in dorks.md)

### For each lead, collect and verify
- Publication name
- Article title and URL (must be live; skip 404s)
- Author name and role (real human > editorial team)
- Contact method + email (confirmed preferred, pattern-inferred accepted)
- Pitch angle (1 sentence tying our pitch to THIS article)
- Blog spear: which Ultra Zoom post fits (see templates.md)
- Send window (Tue–Thu, adjust to author timezone)

### Fields to add to each lead in leads.json
{
  "id": <next in sequence>,
  "publication": "...",
  "article_title": "...",
  "article_url": "...",
  "author": "...",
  "role": "...",
  "contact_email": "...",
  "contact_method": "email | form | linkedin | twitter",
  "contact_confidence": "verified | pattern_inferred | unverified",
  "contact_notes": "...",
  "category": "productivity | privacy | engineering | accessibility | designer |
               genealogy | real-estate | collectors | shopping | students |
               social-media | firefox | general",
  "blog_spear": "privacy-spear | mv3-spear | collector-spear | designer-spear |
                 genealogy-spear | shopping-spear | real-estate-spear |
                 power-tips-spear | listicle-generic | ...",
  "pitch_angle": "...",
  "status": "draft_ready | research_pending",
  "draft_file": "drafts/NN-slug.md"
}

Rules:
- If contact is unverified or pattern-only and you couldn't find a confirmed
  email, set status "research_pending" instead of "draft_ready". Don't write
  a draft file for those yet.
- Continue the id sequence from the last lead in leads.json.
- Draft file numbering: use the lead id, zero-padded if you like
  (31-publication-slug.md).

### Draft emails
For every lead with status "draft_ready":
- Create drafts/NN-publication-slug.md
- Choose the right spear from docs/outreach/templates.md based on blog_spear
- Personalize paragraph 1 with a specific detail from their article
- Keep emails 3–5 short paragraphs, one ask, soft close
- Sign off: Boden Garman / Founder, Lost Rabbit Digital LLC /
  https://ultrazoom.app

### Prioritize
- Chrome/Firefox extension listicle authors with visible, confirmed emails
- Articles published in the last 18 months (current year and the one before)
- Articles with room for one more item (large roundups 20+, "2026" refreshes)
- Independent blogs, small SaaS blogs, niche publications > giant SaaS blogs
- Skip: giant SaaS blogs (HubSpot, ClickUp, Monday, Salesforce) unless there's
  a named author with direct contact
- Skip: content-farm sites with no named author

### Output
- Update docs/outreach/leads.json in place, appending to the leads array
- Create one draft markdown per draft_ready lead
- Print a summary table: id | publication | author | spear | status
- Print a running total: "Leads file now contains X leads (target 300)"

When you're done, ask me whether to commit the changes and push.
```

---

## Routines-compatible prompt (autonomous, PR-at-end)

Schedule via **Claude Routines**. The routine should have access to:
- WebSearch / WebFetch (for finding and verifying articles and contacts)
- GitHub MCP scoped to `lost-rabbit-digital/ultrazoomwebsite`

Paste this block as the routine body:

```
ROUTINE: expand-outreach-prospects
SCHEDULE: every 3 days, 7am PT (or manual)
REPO: lost-rabbit-digital/ultrazoomwebsite
BRANCH: create new branch off main `claude/outreach-batch-YYYY-MM-DD`

GOAL
Add 20–40 new verified prospects to docs/outreach/leads.json, create per-lead
draft emails in docs/outreach/drafts/, commit, and open a PR. Stop when total
leads in the file reach 300.

PRIORITY LANES
1. Chrome/Firefox extension LISTICLE articles (default majority)
2. Niche use-case publications paired with Ultra Zoom blog spears
3. Power-user / "extensions I use daily" personal blogs

STEPS

1. Checkout main, pull latest. Branch: claude/outreach-batch-YYYY-MM-DD.

2. Read docs/outreach/leads.json. If len(leads) >= 300, exit with a no-op
   message "Target of 300 leads already reached; nothing to do."
   Otherwise, read:
   - docs/outreach/dorks.md (search operators)
   - docs/outreach/templates.md (email spear library)
   - docs/outreach/scheduled-log.json if it exists

3. Build a dedupe set from leads.json containing: publication domain,
   article_url, contact_email, author full name.

4. Research pass. Run a mix of searches via WebSearch, using dorks from
   dorks.md:
   - 60% listicle dorks (sections 1–3 of dorks.md, rotating year and
     "best chrome/firefox extensions" phrasing)
   - 40% niche dorks (sections 4–11), biased toward categories with
     fewer than 5 entries in leads.json
   For each promising URL:
   a. WebFetch the article. Skip if 404, paywalled, or auto-generated junk.
   b. Confirm publication is not in the dedupe set.
   c. Extract: publication, article_title, article_url, author name + role,
      publish date.
   d. Try to find a confirmed contact email:
      - WebFetch the /contact or /about page.
      - Look for "firstname@domain" patterns on the site, or in a byline.
      - Check social profiles (twitter/x, linkedin) if email isn't public.
      - Try standard patterns in order: firstname@, firstname.lastname@,
        tips@, editorial@, press@, hello@.
   e. Set contact_confidence:
      "verified" → found a working explicit email on-site
      "pattern_inferred" → guessed from format, looks right
      "unverified" → only a contact form, social DM, or no contact found
   f. If confidence is "unverified", status = "research_pending".
      Else status = "draft_ready".

5. For every draft_ready lead:
   a. Pick the spear from templates.md that best fits blog category.
      Default: listicle-generic.
   b. Write docs/outreach/drafts/<id>-<slug>.md using that template,
      personalizing paragraph 1 with a specific detail from their article
      (author name, subsection, year of update). Do NOT fabricate details.
      If you can't read the article cleanly, fall back to the template's
      generic wording.
   c. Subject, Send window, To fields filled.
   d. Sign-off block:
        Best,
        Boden Garman
        Founder, Lost Rabbit Digital LLC
        https://ultrazoom.app

6. Append new entries to docs/outreach/leads.json (preserve formatting,
   keep leads array sorted by id ascending). Update the "generated" date.

7. Stop when you've added 20–40 leads or explored 10 search queries,
   whichever comes first. Don't add more than 40 per run.

8. Commit to the branch:
     git add docs/outreach/leads.json docs/outreach/drafts/*.md
     git commit -m "outreach: add N prospects (batch YYYY-MM-DD)"
   Push to origin.

9. Open a PR titled:
     "Outreach: N new prospects (YYYY-MM-DD)"
   PR body:
     ## Summary
     Added N outreach prospects via routine. Draft-ready: X. Research-pending: Y.
     Running total: Z / 300.

     ## New leads
     | id | publication | category | spear | status | confidence |
     | ... |

     ## Research notes
     - Queries run: ...
     - Categories biased toward: ...
     - Skipped (duplicates / 404s / paywalls): ...

     ## Next steps
     - Verify any "research_pending" contacts.
     - Run `schedule-outreach-drafts` routine once draft-ready count is >= 10.

GUARDRAILS
- Never modify files outside docs/outreach/leads.json and docs/outreach/drafts/*.
- Never fabricate contact emails. If unsure, mark "unverified" +
  "research_pending".
- Never duplicate an existing publication domain or article URL.
- Skip sites that explicitly forbid cold outreach (e.g., their contact
  page says so). Note them in PR body.
- Cap at 40 new leads per run. Hard stop.
- If WebSearch is rate-limited, commit what you have and open the PR.

EXIT CRITERIA
- PR opened with `outreach` label and (if configured) reviewer = @boden.
- Or: clean no-op if target already reached.
```

---

## Tips for each iteration

- **Listicle-first.** Chrome/Firefox extension roundups reply at roughly 3–5× the rate of niche pubs. Keep them the majority lane until we hit 300.
- **Rotate angles.** If the last batch was heavy on productivity, try accessibility, developer tools, niche lists (photographers, ecommerce, students).
- **Try different platforms.** Medium, Dev.to, Hashnode, Substack, WordPress blogs, YouTube descriptions all yield different-shaped leads.
- **Seasonal hooks.** Back-to-school ("chrome extensions for students 2026"), holiday shopping ("chrome extensions for online shopping"), new year productivity.
- **Spear carefully.** Don't send the engineering spear to a productivity blog or vice versa. `templates.md` has the matching table.
- **Never fabricate contact info.** A `research_pending` lead is more useful than a fabricated "sent" lead that bounces.
- **Run the thin-category bias.** `dorks.md` maintains a list of categories with < 5 leads. Bias every other batch toward those.
