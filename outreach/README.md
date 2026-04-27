# Ultra Zoom + HailBytes outreach pipelines

Two consolidated cold-email lanes that share one Python codebase, one
Google Sheet, and one MailMeteor sender. Both are dispatch-only — no
crons. Re-enable a schedule per workflow once steady-state quality is
verified.

```
                              ┌─ content (Brave/Exa/RSS → Hunter editor) ─┐
   Ultra Zoom outreach ──────►│                                            ├─► UltraZoom tab
                              └─ prospects (Wiza filter → list → enrich) ─┘
                                                                            │
   HailBytes outreach ─────────► prospects (Wiza filter → list → enrich) ──┴─► HailBytes tab
                                                                            │
                                                                MailMeteor reads
                                                                from each tab
                                                                independently.
```

Neither pipeline sends email. MailMeteor handles sending, throttling,
opens/clicks, follow-ups, and reply detection from each tab.

## Repo layout

```
outreach/
  config.py                  env loading, paths, sheet schema, tunable thresholds
  cache.py                   TTL'd JSON file cache for external API calls
  state.py                   persistent dedupe (seen_urls.json, seen_domains.json)
  seeds.py                   content-mode bucket rotation (A–F)
  seeds_uz_companies.txt     prospects-mode UZ seeds (genealogy-flavored B2B)
  seeds_hb_mssp.txt          prospects-mode HB seeds (MSSP + pen-test)
  rss_feeds.txt              curated RSS feed list for content discovery
  excluded_domains.txt       hard-block list (qualify.py reads this)

  discover.py                content discovery orchestrator
  discover_brave.py          Brave Search client
  discover_exa.py            Exa.ai search + findSimilar client
  discover_rss.py            stdlib RSS feed parser
  discover_wiza.py           Wiza prospect-search + prospect-list client
  qualify.py                 hard filters + 0–100 lead_score (content path)
  translate_filters.py       Claude: plain-English seed → Wiza filter object

  enrich_hunter.py           Hunter.io editor lookup
  enrich_verify.py           email verifier (Hunter / NeverBounce / ZeroBounce)
  enrich_personalize.py      Claude personalized opener with validation

  stage_sheet.py             append rows to per-campaign Sheet tab
  run_ultrazoom.py           CLI: Ultra Zoom outreach (--mode content|prospects|both)
  run_hailbytes.py           CLI: HailBytes outreach (Wiza-direct only)

  sync_wiza_lists.py         utility: pull finished Wiza lists by ID (free re-fetch)
  import_wiza_csv.py         utility: parse Wiza CSV email exports (fallback)

  prompts/                   Claude opener templates (per bucket / per campaign)
  state/                     dedupe + rotation state (committed back from CI)
  cache/                     per-API JSON caches
  dropped/                   drop logs by reason; retry queue

.github/workflows/
  outreach-ultrazoom.yml     workflow_dispatch — calls run_ultrazoom
  outreach-hailbytes.yml     workflow_dispatch — calls run_hailbytes
  sync-wiza-lists.yml        workflow_dispatch — calls sync_wiza_lists
  import-wiza-csv.yml        workflow_dispatch — calls import_wiza_csv
```

## Setup

```bash
pip install -r outreach/requirements.txt
```

Required env vars (or GitHub Secrets):

```
WIZA_API_KEY                    # both pipelines, prospects path
ANTHROPIC_API_KEY               # both pipelines (filter translation + opener)
HUNTER_API_KEY                  # UZ content path: editor lookup + verifier
BRAVE_SEARCH_API_KEY            # UZ content path: discovery (one of these two)
EXA_API_KEY                     # UZ content path: discovery
```

Optional:

```
NEVERBOUNCE_API_KEY             # overrides Hunter as the verifier
ZEROBOUNCE_API_KEY              # overrides Hunter as the verifier
GOOGLE_SHEET_ID                 # overrides the default MailMeteor source sheet
```

Google Sheets auth uses Application Default Credentials. In CI,
`google-github-actions/auth@v2` exchanges the workflow's OIDC token for
a short-lived service-account credential — no JSON key. Set repo
variables `GCP_WORKLOAD_IDENTITY_PROVIDER` and `GCP_SERVICE_ACCOUNT`,
and share the target sheet with the SA's email as Editor. See
`docs/outreach/sheets-setup.md`. Locally, `gcloud auth application-default
login` once.

## Running locally

```bash
# Ultra Zoom — both lanes (default), genealogy bucket, ~25 content + ~125 prospects
python -m outreach.run_ultrazoom

# Ultra Zoom — content only (genealogy editors via Brave/Exa/RSS)
python -m outreach.run_ultrazoom --mode content

# Ultra Zoom — prospects only (B2B genealogy contacts via Wiza)
python -m outreach.run_ultrazoom --mode prospects --preview-only  # dry-check match counts first

# HailBytes — MSSP + pen-test, default scale knobs
python -m outreach.run_hailbytes --preview-only  # spend zero credits, just preview

# Dry runs (no external writes, no API spend)
python -m outreach.run_ultrazoom --dry-run --no-reachability
python -m outreach.run_hailbytes --dry-run
```

Defaults are tuned for scale-up runs:

| Pipeline | Lane | Default knobs | Approx output | Wiza credits |
|---|---|---|---|---|
| Ultra Zoom | content | bucket=E, max_stage=25 | up to 25 staged | 0 |
| Ultra Zoom | prospects | seeds=5, profiles=25 | up to 125 staged | ~250 |
| HailBytes | prospects | seeds=5, profiles=25 | up to 125 staged | ~250 |

Drop both numbers (e.g. `--prospects-limit-seeds 1 --prospects-max-profiles 5`)
for a single-row smoke test before you trust a new opener template.

## Sheet schema

Pipelines own these columns on their per-campaign tab. MailMeteor adds
its own (Merge status, Date sent, Opens, Clicks, Replied, Bounced) to
the right when you launch a campaign — pipelines never touch those.

| Column | Source | Used by MailMeteor as |
| --- | --- | --- |
| `discovered_at` | discovery | reference |
| `source` | brave / exa / rss / wiza-prospect | reference |
| `seed_used` | seed that surfaced it | reference |
| `domain` | discovery | reference |
| `recent_post_url` | content: article URL · prospects: LinkedIn URL | `{{recent_post_url}}` |
| `recent_post_title` | content: article title · prospects: job title | `{{recent_post_title}}` |
| `recent_post_description` | discovery | reference |
| `published_date` | discovery | reference |
| `lead_score` | qualification | sort/filter |
| `editor_first_name` | Hunter / Wiza | `{{editor_first_name}}` |
| `editor_last_name` | Hunter / Wiza | `{{editor_last_name}}` |
| `editor_email` | Hunter / Wiza | **To: address** |
| `hunter_confidence` | Hunter / Wiza | reference |
| `email_status` | verifier (always `valid` for staged rows) | filter |
| `personalized_opener` | Claude | `{{personalized_opener}}` |
| `status` | pipeline | `ready_to_send` |
| `enriched_at` | pipeline | reference |
| `notes` | freeform | manual overrides |

## MailMeteor send settings

- **Filter**: `status = ready_to_send` AND `email_status = valid`
- **Daily quota**: 25/day (target middle of 20–30 range)
- **Inter-send delay**: 2–5 minutes random
- **Sending window**: weekdays 9am–1pm Mountain
- **Tracking**: opens + clicks
- **Follow-up**: one auto-follow-up at +5 days, only when no reply

## Recovering Wiza-paid contacts into the Sheet

Wiza occasionally delivers prospect-list results as CSV email
attachments instead of returning contacts on the API path. Two
recovery paths, ordered by preference:

### Preferred: API list sync (free re-fetch)

`outreach/sync_wiza_lists.py` calls `GET /api/lists/{id}/contacts?segment=valid`
for each list_id. **Re-fetching a finished list spends no credits** —
the charge happened at enrichment time. Tab routing comes from the list
name (`UZ —` → UltraZoom, `HB-` → HailBytes).

The list_id is the trailing number in every Wiza email's CSV filename:
`WIZA_*_ID4964965.csv` → list_id `4964965`.

```bash
python -m outreach.sync_wiza_lists 4964965 4964953 4964954 --personalize
python -m outreach.sync_wiza_lists --from-filenames ~/Downloads/WIZA_*.csv
python -m outreach.sync_wiza_lists --auto      # backfill everything finished
```

In CI: trigger `Sync Wiza prospect lists` via `workflow_dispatch` and
paste list IDs into the input.

### Fallback: CSV import

`outreach/import_wiza_csv.py` parses the actual CSV contents — useful
only when the list_id is gone (Wiza purged it, account access lost, etc).
The API sync above is strictly better when it's available.

```bash
python -m outreach.import_wiza_csv ~/Downloads/WIZA_*.csv --personalize
```

## Personalization rules

The Claude prompt enforces, and `validate()` in `enrich_personalize.py`
re-checks:

- ≤25 words (hard cap 30, retry if over 25)
- No em dashes (standing Lost Rabbit Digital preference)
- No sycophantic openers (`I loved`, `great post`, etc.)
- Banned words: `stumbled`, `amazing`
- One sentence, ends with terminal punctuation
- No quotes, no preamble — just the sentence

If the first call fails validation, the pipeline retries once with a
stricter prompt. Two failures drop the candidate. Content-mode
candidates land in `dropped/personalization_failures.jsonl` for
`--retry-failed` reruns.

## Audit checklist

- [x] All API keys via env vars / GitHub Secrets, never hardcoded
- [x] All discovery + enrichment responses cached locally
- [x] State files prevent duplicate outreach across runs
- [x] One-domain-one-outreach rule enforced at qualification (content path)
- [x] Excluded domains list respected (`outreach/excluded_domains.txt`)
- [x] Email verification mandatory before staging
- [x] Pipelines never write to MailMeteor-managed columns
- [x] Pipelines append only, never overwrite or delete
- [x] Personalization output validated for em dashes before staging
- [x] `--dry-run` works end-to-end without external writes
- [x] Service account scoped to one sheet ID
- [x] No active crons — manual dispatch only until quality is verified
