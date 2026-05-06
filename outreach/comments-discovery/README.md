# Ultra Zoom Outreach Pipeline

Discovery + triage tool for finding military/aerospace blog posts where Ultra Zoom can contribute a genuinely useful zoom-and-enhance result in the comments.

## What it does

```
  Exa.ai semantic search        →  candidate URLs
  requests + BeautifulSoup      →  metadata, comment system detection, zoom signal
  filter by score + open comments
  Claude API                    →  drafts a 2-4 sentence suggested comment (or SKIP)
  SQLite                        →  candidates.db
  Flask review UI               →  human triages, edits, marks posted
```

## What it doesn't do

- It does not post comments. That stays human.
- It does not execute JavaScript, so SPAs and lazy-loaded comment widgets may show as `unknown`. Treat those as worth a manual look if the article is otherwise strong.
- It does not add Ultra Zoom links or promo language. The drafted comments are designed to read as genuine contributions; your username on the comment form is your only attribution.

## Setup

```bash
cd ultrazoom_pipeline
python -m venv .venv && source .venv/bin/activate
pip install requests beautifulsoup4 anthropic flask

export EXA_API_KEY=...
export ANTHROPIC_API_KEY=...

python db.py            # creates candidates.db
```

## Run discovery

```bash
# Full run with default queries and AI suggestions
python pipeline.py --verbose

# Cheap dry run (no Claude calls, just discovery)
python pipeline.py --dry-run --verbose

# Custom query
python pipeline.py --query "j-36 prototype photo analysis" --limit 20 --verbose
```

Re-running is idempotent on URL — already-seen candidates are skipped.

## Review

```bash
python review_ui.py
# open http://localhost:5000
```

Workflow per card:
1. Glance at the header image and caption. If it doesn't look zoom-worthy, hit Archive.
2. If it does, click the article link and verify comments are actually open.
3. Run Ultra Zoom on the imagery yourself.
4. Edit the draft to reference what you actually found, paste it into the article's comment box, post.
5. Come back and hit Mark Posted.

## Tuning knobs

- `fetcher.py::ZOOM_SIGNALS` — keyword categories that boost relevance score. Add categories as you find what converts.
- `fetcher.py::_score()` — weights for signal categories vs image count vs word count.
- `pipeline.py::MIN_SCORE` — threshold below which candidates are dropped. Default 0.3.
- `exa_search.py::DEFAULT_ALLOWLIST` — domain allowlist. Trim or expand based on which sites actually accept comments well.
- `exa_search.py::QUERIES` — the seed Exa queries.

## Cost tracking

Every Claude call writes its USD cost to `candidates.suggestion_cost_usd`. The review UI shows running total in the header. At Sonnet pricing, expect ~$0.005 per suggestion, so a run that surfaces 30 fits costs ~$0.15.

## Operating principles

- Quality over volume. Better to post 5 great comments a week than 25 mid ones.
- If two of your posted comments start sounding similar, stop and rewrite.
- If a site's mod team pulls one of your comments, add that domain to an exclude list and don't go back.
- Track conversions: when Stripe shows a new customer, check timing against your `posted_at` log.
