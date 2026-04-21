# Contact-Form Outreach — Workflow

A parallel lane to the email outreach flow (see `iteration-prompt.md` +
`gmail-drafts-prompt.md`). Contact forms hit the right inbox, skip most spam
filters, and require no contact-enrichment step — so for listicles where a
quick pitch is enough, this is faster than cold email.

**Target cadence:** 20–40 form submissions per week split across you and
your cofounder, zero-research overhead per lead beyond "is this page a real
fit?"

**Budget constraint this lane solves:** the 50 emails/month ceiling. Form
submissions aren't capped by email sending limits.

## Pipeline at a glance

```
exa-queries.md  ─┐
                 ├─►  GH Action (daily cron)  ─►  find-leads.mjs  ─►  Google Sheet (shared)
leads.json URLs ─┘                                                         │
   (find-similar seeds)                                                    ▼
                                                             you + cofounder triage,
                                                             submit, track in-sheet
```

One-time setup: **`sheets-setup.md`** (service account, sheet creation,
GitHub secrets). ~20 minutes under boden@lostrabbitdigital.com.

## 1. Discovery (automatic, daily)

`.github/workflows/find-leads.yml` runs at 13:00 UTC daily and calls
`scripts/find-leads.mjs` in `both` mode. It:

- Runs the natural-language queries in `docs/outreach/exa-queries.md`
  against Exa's `/search`.
- Runs `/findSimilar` on every article URL in `docs/outreach/leads.json`.
- Dedupes against URLs already in the Sheet.
- Appends only new rows. **It never edits existing rows**, so human status
  edits are safe across runs.

You can also trigger it manually: Actions tab → **Find leads** → **Run
workflow**, optionally picking `mode`, `limit`, or a `sections` regex.

### Running it locally

```
export EXA_API_KEY=...
export GOOGLE_SHEETS_SA_KEY="$(cat path/to/sa-key.json)"
export LEADS_SHEET_ID=...

npm run find-leads -- --mode search --limit 10
npm run find-leads -- --mode find-similar --limit 20
npm run find-leads -- --dry-run --limit 5     # preview without API calls
```

## 2. Triage in the Sheet

For each `status = new` row:

1. Open the URL. 5-second yes/no: is this a real listicle or niche article
   where Ultra Zoom genuinely fits?
   - **No** → `status = kill`. Leave row (it's a useful dedup anchor).
   - **Yes** → continue.
2. Pick a `template` id from `contact-form-templates.md` (`form-listicle`,
   `form-photo-design`, `form-shopping`, `form-genealogy`,
   `form-real-estate`, `form-privacy`, `form-generic`).
3. Find the site's contact form (usually `/contact`, `/about`, or in the
   footer). Paste the URL into `contact_url`. If there's no form and only
   a bare email, move the lead to the email flow (`leads.json`) — don't
   duplicate here.
4. Set `assigned_to` to your name so your cofounder doesn't pick the same
   row.
5. `status = triaged`.

## 3. Submit

Open each row where `assigned_to = you` and `status = triaged`:

1. Copy the template from `contact-form-templates.md`.
2. Replace `ARTICLE_TITLE`, `PUBLICATION`, `SECTION` with the row's values.
3. Paste into the form. One URL max in the body. No markdown. Submit.
4. In the Sheet: `status = submitted`, `message_sent = YYYY-MM-DD`, any
   quirks in `notes` (captcha, auto-responder, etc.).

## 4. Track replies

- Reply lands → `status = replied_positive` / `replied_negative`, paste a
  quote or summary into `reply`.
- Article gets updated to include Ultra Zoom → `status = linked`, note the
  date in `notes`. These become backlink wins we can cite later.

## 5. Sheet schema

The script writes these columns (see `scripts/lib/sheets.mjs` for the
canonical list):

| Column | Filled by | Notes |
|---|---|---|
| `found_at` | script | ISO date of discovery |
| `source` | script | `exa-search` or `exa-similar` |
| `seed` | script | the query (search) or seed URL (find-similar) that surfaced this |
| `title` | script | article title from Exa |
| `url` | script | dedupe key |
| `domain` | script | hostname, no `www.` |
| `published_date` | script | Exa-reported publish date (often blank) |
| `summary` | script | first ~300 chars of article text |
| `status` | human | see values below |
| `template` | human | template id |
| `contact_url` | human | direct URL to the form |
| `assigned_to` | human | who owns this lead |
| `message_sent` | human | ISO date |
| `reply` | human | quote or summary |
| `notes` | human | anything else |

### Status values

| Value | Meaning |
|---|---|
| `new` | Just discovered. Needs triage. |
| `kill` | Not a fit. |
| `triaged` | Reviewed, template picked, contact URL confirmed, assigned. |
| `submitted` | Message posted. `message_sent` set. |
| `replied_positive` | Reply received, willing to list / update. |
| `replied_negative` | Decline. |
| `linked` | Ultra Zoom visible in the article. |
| `no_reply` | 30+ days since submit, nothing heard. |
| `bounced` | Form failed (captcha, 500, auto-reject). |

## 6. When to escalate a lead to email instead

Use the email flow (`leads.json`) when:
- The publication is high-tier (10k+ readers) and worth personalizing for.
- You already have a blog-post spear that perfectly matches the niche.
- The author's byline links to a personal email.

Use this lane (contact form) when:
- Generic "best extensions" listicle.
- Contact form is the only surface.
- You just want volume and the pitch is straightforward.

## 7. Maintaining query quality

- When a `find-similar` lead is outstanding, reverse-engineer it: add a new
  query to `exa-queries.md` describing that article's *shape* so `search`
  mode will surface more like it.
- If a `sections` regex stops producing `triaged`-worthy results, tighten
  the language in those bullets — Exa rewards specificity.
- Periodically promote your best `status = linked` articles by adding
  their URLs to `leads.json` (even as already-contacted) so future
  `find-similar` passes use them as high-quality seeds.
