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
exa-queries.md  ──►  Find leads (Exa)   ─┐
leads.json URLs ──►  (13:00 UTC)         │
                                         ├─►  find-leads.mjs  ─►  Google Sheet (shared)
dorks.md        ──►  Find leads (Brave)  ─┘          │                  │
                     (15:00 UTC)                     ▼                  ▼
                                        contact-form auto-probe   you + cofounder
                                        fills contact_url when    triage, submit,
                                        detectable                track in-sheet
```

One-time setup: **`sheets-setup.md`** (service account, sheet creation,
GitHub secrets). ~20 minutes under boden@lostrabbitdigital.com.

## 1. Discovery (automatic, daily)

Two GitHub Actions workflows write to the same Sheet:

- `.github/workflows/find-leads.yml` — **Find leads (Exa)** at 13:00 UTC.
  Runs NL queries from `docs/outreach/exa-queries.md` against Exa's
  `/search`, and `/findSimilar` on every article URL in
  `docs/outreach/leads.json`.
- `.github/workflows/find-leads-brave.yml` — **Find leads (Brave)** at
  15:00 UTC. Runs Google-style dorks from `docs/outreach/dorks.md` against
  the Brave Search API. `YEAR` tokens are auto-substituted with the current
  year; other placeholders (NICHE, BLOG_SPEAR, SUBREDDIT) are skipped.

Both workflows:

- Dedupe against URLs already in the Sheet (global, across providers).
- Append only new rows. **They never edit existing rows**, so human status
  edits are safe across runs.
- Run a best-effort contact-form probe on each new URL and pre-fill
  `contact_url` when a form is detected (see §2 and §5 below).

Trigger either manually: Actions tab → **Find leads (Exa)** or **Find
leads (Brave)** → **Run workflow**, optionally picking `mode`, `limit`,
`sections` regex, or `since` date.

### Running it locally

```
export GOOGLE_SHEETS_SA_KEY="$(cat path/to/sa-key.json)"
export LEADS_SHEET_ID=...

# Exa provider
export EXA_API_KEY=...
npm run find-leads -- --provider exa --mode search --limit 10
npm run find-leads -- --provider exa --mode find-similar --limit 20

# Brave provider
export BRAVE_SEARCH_KEY=...
npm run find-leads -- --provider brave --limit 20
npm run find-leads -- --provider brave --sections "Listicle" --limit 5

# Dry run (no API, no Sheet writes) — works with either provider
npm run find-leads -- --provider exa --dry-run --limit 5
npm run find-leads -- --provider brave --dry-run --limit 5

# Skip contact-form auto-probe (faster, useful when debugging)
npm run find-leads -- --provider exa --no-detect --limit 5

# Write to a local CSV instead of Google Sheets (skips SA/key setup)
npm run find-leads -- --provider exa --csv leads.csv --limit 10
```

### Smoke-testing in CI before Sheets is configured

Both workflows accept a `csv` boolean input on manual dispatch. Running
with `csv: true` skips the `GOOGLE_SHEETS_SA_KEY` / `LEADS_SHEET_ID`
checks, writes results to `leads-<provider>-<timestamp>.csv`, and uploads
that file as a workflow artifact (14-day retention). You only need the
provider API key secret set (`EXA_API_KEY` or `BRAVE_SEARCH_KEY`) for
this to work. Download the artifact from the run page to inspect the
rows before committing to the Sheets setup.

## 2. Triage in the Sheet

For each `status = new` row:

1. Open the URL. 5-second yes/no: is this a real listicle or niche article
   where Ultra Zoom genuinely fits?
   - **No** → `status = kill`. Leave row (it's a useful dedup anchor).
   - **Yes** → continue.
2. Pick a `template` id from `contact-form-templates.md` (`form-listicle`,
   `form-photo-design`, `form-shopping`, `form-genealogy`,
   `form-real-estate`, `form-privacy`, `form-generic`).
3. Confirm the contact form:
   - If `contact_url` is already filled (the script auto-detected one),
     open it and verify the form actually loads and looks right. Keep as-is
     or correct it.
   - If `contact_url` is blank, hunt for a form manually (`/contact`,
     `/about`, footer links). Paste the URL into `contact_url`. If there's
     no form and only a bare email, move the lead to the email flow
     (`leads.json`) — don't duplicate here.
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
| `source` | script | `exa-search`, `exa-similar`, or `brave-search` |
| `seed` | script | the query (search) or seed URL (find-similar) that surfaced this |
| `title` | script | article title from the provider |
| `url` | script | dedupe key |
| `domain` | script | hostname, no `www.` |
| `published_date` | script | provider-reported publish date (often blank) |
| `summary` | script | first ~300 chars of article text / description |
| `status` | human | see values below |
| `template` | human | template id |
| `contact_url` | script + human | auto-filled when the probe finds a form; verify during triage, correct if wrong |
| `assigned_to` | human | who owns this lead |
| `message_sent` | human | ISO date |
| `reply` | human | quote or summary |
| `notes` | human | anything else |

### About the `contact_url` auto-probe

After each provider returns results, the script HEAD/GETs ~16 common
contact paths on the article's origin (`/contact`, `/contact-us`,
`/about`, `/write-for-us`, …) with a short per-URL budget. If it finds a
page that contains a `<form>` with textarea/email input or an embed from
a known form provider (Formspree, Typeform, JotForm, HubSpot, etc.), that
URL lands in `contact_url`. It's best-effort:

- **False negatives** happen on JS-rendered forms, Cloudflare-challenged
  pages, or unusual path names. Blank `contact_url` is not proof there's
  no form — still do a 10-second manual check during triage.
- **False positives** are rare but possible (e.g. a page that embeds an
  unrelated newsletter form). Always open the URL before submitting.

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
