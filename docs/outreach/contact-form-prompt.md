# Contact-Form Outreach — Workflow

A parallel lane to the email outreach flow (see `iteration-prompt.md` +
`gmail-drafts-prompt.md`). Contact forms hit the right inbox, skip most spam
filters, and require no contact-enrichment step — so for listicles where a
quick pitch is enough, this is faster than cold email.

**Target cadence:** 20–40 form submissions per week with zero research
overhead per lead beyond "is this page a real fit?"

**Budget constraint this lane solves:** the 50 emails/month ceiling. Form
submissions aren't capped by email sending limits.

## Pipeline at a glance

```
dorks.md  ──►  find-leads.mjs  ──►  leads-contact-form.csv
                                            │
                                            ▼
                                    Google Sheets import
                                            │
                                            ▼
                             triage → pick template → submit → track
```

## 0. One-time setup

1. Get Google Custom Search API creds (see header of `scripts/find-leads.mjs`
   for the 5-step setup). Export:
   ```
   export GOOGLE_CSE_KEY=...
   export GOOGLE_CSE_ID=...
   ```
2. Import `docs/outreach/leads-contact-form.csv` into a Google Sheet once it
   exists. Use **File → Import → Upload → Replace current sheet** (first row
   is the header). Freeze the header row.
3. Set a conditional-format rule on the `status` column: green for
   `submitted` / `linked`, red for `kill` / `bounced`, yellow for
   `replied_*`.

## 1. Discover

Run the dork script. Defaults write to `docs/outreach/leads-contact-form.csv`
and append new rows only (URL-level dedupe against the existing file).

```
# preview which queries would run
npm run find-leads -- --dry-run --limit 20

# run listicle + niche sections only, 10 queries
npm run find-leads -- --sections "listicle|niche|photography|shopping" --limit 10

# run everything (respect the 100 query/day free quota)
npm run find-leads -- --limit 80
```

Expected yield: ~4–8 usable rows per dork after dedupe + domain filter.

## 2. Triage in the Sheet

Re-import the updated CSV (or copy-paste the new rows). For each `new` row:

- Open the URL. 5-second yes/no: is this a real listicle or niche article
  where Ultra Zoom genuinely fits?
  - **No** → set `status = kill`. Move on.
  - **Yes** → continue.
- Pick a template id from `contact-form-templates.md` and put it in the
  `template` column (`form-listicle`, `form-photo-design`,
  `form-shopping`, `form-genealogy`, `form-real-estate`, `form-privacy`,
  `form-generic`).
- Hunt for the contact page on the same domain (usually `/contact`,
  `/about`, footer link, or author bio). Paste it into `contact_url`.
  - If there is no contact form and only a bare email, move the lead to
    the email flow (`leads.json`) — don't duplicate it here.
- Set `status = triaged`.

## 3. Submit

Open each `triaged` row:

1. Copy the template from `contact-form-templates.md`.
2. Replace `ARTICLE_TITLE`, `PUBLICATION`, `SECTION` with the values from
   the row.
3. Paste into the contact form.
4. Submit.
5. In the Sheet: set `status = submitted`, `message_sent` = today's date,
   and any quirks in `notes` (captcha, "I'll hear back in 2 weeks",
   auto-responder text, etc.).

**Submission hygiene reminders:**
- One URL max in the message body.
- No markdown.
- Don't mention Pro on first touch.

## 4. Track replies

When a reply comes back, update `status` to `replied_positive` /
`replied_negative`. Drop the reply quote or a summary into `reply`.

When the article gets updated to include Ultra Zoom, set `status = linked`
and note the date in `notes`. These become backlink wins we can cite in
later outreach.

## 5. CSV schema

| Column | Filled by | Notes |
|---|---|---|
| `found_at` | script | ISO date of discovery |
| `category` | script | dork section heading |
| `query` | script | exact dork that surfaced this row |
| `rank` | script | position in CSE results (1–10) |
| `title` | script | page `<title>` from Google |
| `url` | script | dedupe key |
| `domain` | script | `url`'s hostname (no `www.`) |
| `snippet` | script | first ~240 chars of CSE snippet |
| `status` | human | see status table in `contact-form-templates.md` |
| `template` | human | template id from `contact-form-templates.md` |
| `contact_url` | human | direct link to the form |
| `message_sent` | human | ISO date of submission |
| `reply` | human | quote or summary of reply |
| `notes` | human | anything else (captcha, auto-reply, etc.) |

## 6. Re-running

- The script appends + dedupes, so you can run it weekly without creating
  duplicate rows.
- Roll any Reddit `after:YYYY-MM-DD` date cutoffs forward in `dorks.md`
  every couple of months.
- If a dork section stops producing `triaged`-worthy results, remove it from
  the `--sections` filter instead of editing `dorks.md`.

## 7. When to escalate to email instead

Use email (the `leads.json` flow) when:
- The publication has 10k+ readers and is worth personalizing for.
- You already have a spear blog post that directly matches the niche.
- The author has a personal byline + findable email and the contact form
  routes to a shared inbox.

Use this lane (contact form) when:
- The page is a generic "best extensions" listicle.
- The site has a contact form but no individual author email.
- You just need volume and the pitch is straightforward.
