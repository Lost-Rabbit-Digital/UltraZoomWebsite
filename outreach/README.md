# Ultra Zoom outreach pipelines

Manual Apollo CSV in, personalized email drafts out. The pipeline reads
a CSV exported from a saved Apollo people-search, asks Claude to draft
a Touch 1 + Touch 2 per row, and appends the results to two tabs of a
campaign-specific Google Sheet. MailMeteor imports each tab to send the
two touches as separate campaigns spaced ~5 days apart.

The HailBytes pipelines (ASM and SAT) live in `hailbytes-static`. This
repo only owns the Ultra Zoom side: Realtors and Press.

```
                  ┌──────────────────┐
   manual         │  Apollo people   │
   Apollo UI ──── │  search → CSV    │ ─── drop in ────┐
   export         └──────────────────┘                 │
                                                       ▼
                                       outreach/inbox/<campaign>/<date>.csv
                                                       │
                                                       │  push triggers GH Action
                                                       ▼
                              ┌──────────────────────────────────────┐
                              │ run_ultrazoom.py --campaign <name>   │
                              │  · ingest CSV                        │
                              │  · dedupe vs. existing sheet rows    │
                              │  · per lead: T1 + T2 via Claude      │
                              │  · validate (em-dashes, banned       │
                              │    words, required merge tags)       │
                              │  · stage to <Campaign>_T1 tab        │
                              │  · stage to <Campaign>_T2 tab        │
                              └──────────────────────────────────────┘
                                                       │
                                                       ▼
                                          ┌──────────────────────┐
                                          │ Google Sheet (per    │
                                          │ campaign, two tabs)  │
                                          └──────────────────────┘
                                                       │
                                                       ▼
                                          MailMeteor imports each
                                          tab as a separate send
```

The pipeline does not send email. MailMeteor handles sending,
throttling, opens/clicks, and reply detection per-tab.

## Repo layout

```
outreach/
  README.md                        this file
  __init__.py
  config.py                        env loading, paths, base sheet schema
  campaign_config.py               per-campaign config (tabs, prompts, voice rules)
  cache.py                         JSON file cache used by enrich_verify

  ingest_apollo_csv.py             read Apollo CSV → candidate dicts
  enrich_verify.py                 optional Hunter/NeverBounce/ZeroBounce verifier
  enrich_personalize.py            Claude T1+T2 drafting with prompt caching
  stage_sheet.py                   append to per-tab Sheet schema
  run_ultrazoom.py                 CLI: --campaign realtors | press

  excluded_domains.txt             hard-block list

  inbox/                           Apollo CSVs land here, by campaign
    ultrazoom-realtors/
    ultrazoom-press/

  prompts/                         per-touch reference templates
    ultrazoom_realtors_touch1.md
    ultrazoom_realtors_touch2.md
    ultrazoom_press_touch1.md
    ultrazoom_press_touch2.md

  campaigns/                       campaign briefs (strategy + Apollo filters)
    ultrazoom-realtors-q2-2026.md
    ultrazoom-press-q2-2026.md

.github/workflows/
  outreach-ultrazoom.yml           workflow_dispatch + push:outreach/inbox/**
```

## Setup

```bash
pip install -r outreach/requirements.txt
```

Required env vars (or GitHub Secrets):

```
ANTHROPIC_API_KEY                 personalization (both campaigns)
GOOGLE_SHEET_ID_UZ_REALTORS       campaign-specific Sheets target
GOOGLE_SHEET_ID_UZ_PRESS          campaign-specific Sheets target
```

Optional:

```
HUNTER_API_KEY / NEVERBOUNCE_API_KEY / ZEROBOUNCE_API_KEY
    Re-verify Apollo emails before personalization. Apollo's saved
    search already filters to Verified, so this is belt-and-braces.
```

Google Sheets auth uses Application Default Credentials. In CI,
`google-github-actions/auth@v2` exchanges the workflow's OIDC token
for a short-lived service-account credential — no JSON key. Set repo
variables `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`,
and share the target sheet with the SA's email as Editor. See
`docs/outreach/sheets-setup.md`. Locally, run
`gcloud auth application-default login` once.

## Running locally

```bash
# Realtors campaign
python -m outreach.run_ultrazoom --campaign realtors

# Press campaign
python -m outreach.run_ultrazoom --campaign press

# Smoke test against a sample CSV without spending API credit
python -m outreach.run_ultrazoom --campaign realtors --dry-run

# Pin to a specific CSV (otherwise the latest by mtime in the
# campaign's inbox folder is used)
python -m outreach.run_ultrazoom --campaign realtors \
    --inbox-csv outreach/inbox/ultrazoom-realtors/2026-04-29.csv

# Cap the number of leads processed (good for first-batch sanity)
python -m outreach.run_ultrazoom --campaign realtors --limit 5
```

## Sheet schema

Each campaign has two tabs in a campaign-specific Sheet. Pipeline owns
the columns below; MailMeteor adds its own (Merge status, Date sent,
Opens, Clicks, Replied, Bounced) to the right and the pipeline never
touches them.

| Column | Source | Used by MailMeteor as |
| --- | --- | --- |
| `discovered_at` | ingest | reference |
| `source` | ingest (`apollo-csv-<campaign>`) | reference |
| `first_name` | Apollo | `{{first_name}}` |
| `last_name` | Apollo | reference |
| `editor_email` | Apollo | **To: address** |
| `editor_title` | Apollo | reference |
| `company` | Apollo | `{{company}}` / `{{publication}}` (press) |
| `domain` | parsed from Apollo Website | reference |
| `linkedin_url` | Apollo | reference |
| `city` | Apollo | reference |
| `state` | Apollo | reference |
| `industry` | Apollo | reference |
| `keywords` | Apollo | reference (signal mining for AI prompt) |
| `apollo_contact_id` | Apollo | hard dedupe key |
| `personalized_subject` | Claude | **MailMeteor Subject** |
| `personalized_body` | Claude | **MailMeteor Body** |
| `status` | pipeline | filter (`= ready_to_send`) |
| `enriched_at` | pipeline | reference |
| `notes` | pipeline (campaign + touch + sender) | reference |

Press T1 also has `specific_recent_topic` (empty when staged; Boden
fills before MailMeteor send).

## MailMeteor send settings

- **Filter:** `status = ready_to_send`
- **Daily quota:** 15 hard limit on the sender mailbox
- **Subject:** `{{personalized_subject}}`
- **Body:** `{{personalized_body}}`
- **Sending window:** weekdays, recipient local hours
- **Tracking:** opens + clicks
- **Threading:** Touch 2 imported separately ~5 send-days after Touch 1.
  T2 subject is `Re: <T1 subject>` so Gmail threads it.

## Personalization rules

The Claude prompt enforces and the validator re-checks:

- Subject: ≤ 9 words
- Body: 50–180 words (campaign config can lower the upper bound)
- No em-dashes (period or comma instead)
- No sycophancy (`I love`, `great post`, `really enjoyed`, etc.)
- Banned words: `stumbled`, `amazing`, `revolutionize`, `leverage`,
  `synergy`, `robust solution`, `cutting-edge`, `world-class`
- One-shot retry with a stricter prompt on validation failure;
  candidate is dropped after two failures
- Required merge tags must appear in the body verbatim:
  - Realtors T1: `{{landing_page_link}}`, `REALTOR30`
  - Realtors T2: `REALTOR30`
  - Press T1: `{{specific_recent_topic}}`, `{{press_kit_link}}`
  - Press T2: `{{license_signup_link}}`

## Audit checklist

- [x] All API keys via env vars / GitHub Secrets, never hardcoded
- [x] Verifier responses cached locally (`outreach/cache/verify_cache.json`)
- [x] Sheet-side dedupe at append time (existing `editor_email` rows skipped)
- [x] Pipeline never writes to MailMeteor-managed columns
- [x] Pipeline appends only, never overwrites or deletes
- [x] Personalization output validated before staging
- [x] `--dry-run` works end-to-end without external writes
- [x] Service account scoped per-sheet (one campaign = one Sheet)
- [x] No active crons — manual dispatch + push-triggered only
- [x] `excluded_domains.txt` honored at ingest time
- [x] Apollo "verified-only" filter is enforced again on the read side
