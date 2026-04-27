# Ultra Zoom outreach pipeline

A self-contained discover → qualify → enrich → stage workflow that drops
cold-email candidates into a Google Sheet that MailMeteor reads as a
mail-merge source.

```
discover (Brave + Exa + RSS)
  → qualify (hard filters + 0–100 score, dedupe vs. state files)
  → enrich (Hunter editor lookup, email verification, Claude opener)
  → stage  (append rows to MailMeteor source sheet)
```

This pipeline does **not** send email, schedule sends, manage follow-ups,
or detect replies. MailMeteor handles all of that off-cluster.

## Repo layout

```
outreach/
  config.py                  env loading, paths, thresholds, sheet schema
  seeds.py                   seed-keyword buckets + rotation state
  discover_brave.py          Brave Search client
  discover_exa.py            Exa.ai search + findSimilar client
  discover_rss.py            RSS feed parser (stdlib only)
  discover.py                orchestrator that fans out across all sources
  qualify.py                 hard filters + 0–100 lead_score
  enrich_hunter.py           Hunter.io editor lookup
  enrich_verify.py           NeverBounce / ZeroBounce verifier
  enrich_personalize.py      Claude opener with validation + 1 retry
  stage_sheet.py             Sheets append (service-account JWT, stdlib auth)
  run_pipeline.py            CLI orchestrator
  state/                     dedupe + rotation state (committed back from CI)
  cache/                     per-API JSON caches
  dropped/                   drop logs by reason; retry queue
  prompts/personalization.md Claude prompt template
  excluded_domains.txt       hard-block domains
  rss_feeds.txt              curated RSS feed list
```

## Setup

Install dependencies:

```bash
pip install -r outreach/requirements.txt
```

Set env vars (or GitHub Secrets for the cron):

```
BRAVE_SEARCH_API_KEY
EXA_API_KEY
HUNTER_API_KEY                 # used for editor lookup AND email verification
ANTHROPIC_API_KEY
```

Optional:
```
GOOGLE_SHEET_ID                # override the default MailMeteor sheet
NEVERBOUNCE_API_KEY            # overrides Hunter's verifier when set
ZEROBOUNCE_API_KEY             # overrides Hunter's verifier when set
SERPAPI_KEY                    # SERP fallback (not yet used by default)
RSS_FEED_LIST_PATH             # override the curated feed list
```

**Email verification**: Hunter's `/v2/email-verifier` is the default — same
key as the editor lookup, no second vendor needed. NeverBounce or
ZeroBounce are optional secondary checks; when one is set it takes
priority over Hunter (slightly better at catch-all detection at higher
volumes).

**Google Sheets auth**: uses Application Default Credentials. In CI,
`google-github-actions/auth@v2` exchanges the workflow's OIDC token for
a short-lived service-account credential — no JSON key needed. Repo
variables `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`
must be set (shared with the find-leads workflow; see
`docs/outreach/sheets-setup.md`). Locally, run `gcloud auth
application-default login` once. Either way, the service account must
have **Editor** access on the target sheet — share the sheet directly
with the SA's email.

## Running locally

```bash
# Full pipeline, default budget (15 staged rows max).
python -m outreach.run_pipeline

# Dry run — log every action, write nothing external. Skips reachability
# probes if you're offline.
python -m outreach.run_pipeline --dry-run --no-reachability

# Discovery only — populate state, skip enrich and stage.
python -m outreach.run_pipeline --discover-only

# Override the seed bucket rotation.
python -m outreach.run_pipeline --bucket A

# Re-run personalization for previously failed candidates.
python -m outreach.run_pipeline --retry-failed

# Use Sonnet instead of Haiku for personalization (higher cost, sharper output).
python -m outreach.run_pipeline --model sonnet
```

## Sheet schema

The pipeline owns these columns in the `Leads` tab. MailMeteor adds its
own columns (Merge status, Date sent, Opens, Clicks, Replied, Bounced)
to the right when you launch a campaign — the pipeline never touches
those.

| Column | Source | Used by MailMeteor as |
| --- | --- | --- |
| `discovered_at` | discovery | reference |
| `source` | brave / exa / exa-similar / rss | reference |
| `seed_used` | the seed that surfaced it | reference |
| `domain` | discovery | reference |
| `recent_post_url` | discovery | `{{recent_post_url}}` |
| `recent_post_title` | discovery | `{{recent_post_title}}` |
| `recent_post_description` | discovery | reference |
| `published_date` | discovery | reference |
| `lead_score` | qualification | sort/filter |
| `editor_first_name` | Hunter | `{{editor_first_name}}` |
| `editor_last_name` | Hunter | `{{editor_last_name}}` |
| `editor_email` | Hunter | **To: address** |
| `hunter_confidence` | Hunter | reference |
| `email_status` | Hunter (or NeverBounce/ZeroBounce) | always `valid` for staged rows |
| `personalized_opener` | Claude | `{{personalized_opener}}` |
| `status` | pipeline | always `ready_to_send` |
| `enriched_at` | pipeline | reference |
| `notes` | freeform | manual overrides |

## MailMeteor campaign template

In MailMeteor, create a campaign reading from the same sheet. Use the
following template — every `{{name}}` matches a column header above
exactly:

```
Subject: Quick note about {{recent_post_title}}

Hi {{editor_first_name}},

{{personalized_opener}}

[Boden writes the body here — Ultra Zoom pitch + ask for inclusion.]

Thanks,
Boden McHale
Lost Rabbit Digital
https://ultrazoom.app
```

Recommended send settings:

- **Filter**: `status = ready_to_send` AND `email_status = valid`
- **Daily quota**: 25/day (target middle of 20–30 range)
- **Inter-send delay**: 2–5 minutes random
- **Sending window**: weekdays 9am–1pm Mountain
- **Tracking**: opens + clicks
- **Follow-up**: one auto-follow-up at +5 days, only when no reply

## Seed buckets

Seeds rotate across four buckets so each run pulls from a different
angle. State persists in `state/seed_rotation_state.json` — the cron
commits it back so the rotation does not loop on restart.

| Bucket | Angle |
| --- | --- |
| A | Listicle hunting (browser/extension roundups) |
| B | Use-case roundups (where Ultra Zoom solves a pain) |
| C | Adjacent communities (designers, accessibility, e-commerce) |
| D | Resource directories |

`[year]` in seeds is templated to the current year and the previous year
at runtime.

## Qualification scoring

Hard filters: `seen_urls` / `seen_domains` dedupe, `excluded_domains.txt`,
recency (≤24 months when a date is present), English language, HTTP
reachability, non-empty title + description.

Score (0–100, threshold 50 to advance):

| Signal | Δ |
| --- | --- |
| listicle terms in title (`best`, `top`, `essential`) | +20 |
| year / "updated" in title | +10 |
| roundup / directory / toolbox terms | +15 |
| extension + browser terms in body | +15 |
| designer / UX terms | +10 |
| accessibility terms | +10 |
| productivity terms | +5 |
| privacy terms | +10 |
| source = RSS | +10 |
| source = exa-similar from a known-good target | +15 |
| spam terms (sponsored / paid) | −20 |
| domain on soft watch list (medium, dev.to, etc.) | −15 |

## Drop behaviour

Candidates that pass hard filters but fail enrichment are logged to
`outreach/dropped/dropped.jsonl` with one of these statuses:

| Status | Meaning |
| --- | --- |
| `no_editor_found` | Hunter returned no usable contact |
| `bad_email` | Verifier returned `invalid` |
| `manual_review` | Verifier returned `risky` or `unknown` |
| `verify_error` | Transient verifier failure |
| `personalization_failed` | Claude couldn't produce a valid opener |
| `below_threshold` | (in qualifier stats only) score < 50 |

`personalization_failed` candidates are also appended to
`outreach/dropped/personalization_failures.jsonl` so `--retry-failed`
can re-run only that subset.

## Personalization rules

The Claude prompt enforces, and `validate()` in
`enrich_personalize.py` re-checks:

- ≤25 words (hard cap 30, retry if over 25)
- No em dashes (standing Lost Rabbit Digital preference)
- No sycophantic openers (`I loved`, `great post`, etc.)
- Banned words: `stumbled`, `amazing`
- One sentence, ends with terminal punctuation
- No quotes, no preamble — just the sentence

If the first call fails validation, the pipeline retries once with a
stricter prompt. Two failures drop the candidate.

## Cost expectations (monthly, ~25 sends/day)

| Service | Estimate |
| --- | --- |
| Brave Search API | ~$5 (free tier covers most use) |
| Exa.ai | $10–20 |
| Hunter.io Starter | $49 (covers editor lookup + email verification) |
| Anthropic API (Haiku) | $3–5 |
| MailMeteor Premium | $10 |
| **Total** | **~$77–95/month** |

NeverBounce/ZeroBounce add ~$5/mo if you want a dedicated verifier on top.

## Audit checklist

- [x] All API keys via env vars / GitHub Secrets, never hardcoded
- [x] All discovery + enrichment responses cached locally
- [x] State files prevent duplicate outreach across runs
- [x] One-domain-one-outreach rule enforced at qualification
- [x] Excluded domains list respected
- [x] Email verification mandatory before staging
- [x] Pipeline never writes to MailMeteor-managed columns
- [x] Pipeline appends only, never overwrites or deletes
- [x] Personalization output validated for em dashes before staging
- [x] `--dry-run` works end-to-end without external writes
- [x] Service account scoped to one sheet ID
- [x] Seed bucket rotation produces variety
- [x] README documents MailMeteor template setup with exact merge field names
- [ ] Cost-per-run logging (TODO: emit to GITHUB_STEP_SUMMARY)

## Importing Wiza CSV exports (email lane)

Wiza occasionally delivers prospect-list results as CSV email attachments
(e.g. when a list was kicked off in the Wiza UI rather than via the API,
or when the API path failed mid-poll). Those credits already burned, so
`outreach/import_wiza_csv.py` ingests the CSVs and lands the rows in the
same per-campaign tabs the API path writes to.

```bash
# Local: download the CSVs from the Wiza email, then point the importer
# at them. Filename prefix decides the tab — WIZA_uz_* → UltraZoom,
# WIZA_hb_* → HailBytes (override with --tab).
python -m outreach.import_wiza_csv ~/Downloads/WIZA_*.csv --personalize

# CI: paste the email's download URLs (one per line) into the
# `Import Wiza CSV exports` workflow_dispatch input. The workflow
# downloads each URL, then runs the importer with the same flags.
```

Flags worth knowing:

- `--include-no-email` — also append rows where Wiza couldn't find an
  email (`status = manual_review` so MailMeteor's `ready_to_send` filter
  excludes them). Deduped against the tab's existing `recent_post_url`
  column, so re-runs are idempotent.
- `--no-personalize` — skip Claude opener generation (e.g. when you
  want to bulk-stage and personalize manually later).
- `--limit N` — cap rows per CSV; useful for a smoke test before
  unloading the full file.

## Manual end-to-end first run

1. Configure all GitHub Secrets above.
2. Trigger `Outreach pipeline` workflow with `dry_run = true` to confirm
   discovery and qualification work without writes.
3. Re-trigger with `dry_run = false` and `max_stage = 1` to stage a
   single row.
4. Open the sheet, confirm the row's columns look right, then build the
   MailMeteor campaign with the template above.
5. Send the row to a test inbox you control. Confirm all merge fields
   render.
6. Bump `max_stage` back to 15 and let the cron handle steady-state.
