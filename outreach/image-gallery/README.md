# Ultra Zoom image-gallery pipeline

Discovery → AI upscale → human review → Imgur public-gallery posting →
analytics. Same shape as `outreach/comments-discovery`, different surface
area.

## What it does

```
  Reddit / Wikimedia Commons / NASA APOD / Exa.ai     ── Stage 1 ──▶ candidates/
                                                                     gallery.db
  ONNX Real-ESRGAN x4plus  +  watermark  +  resize    ── Stage 2 ──▶ enhanced/
                                                                     (status='enhanced')
  Flask review UI: side-by-side compare, approve,     ── Stage 3 ──▶ queue rows
  edit title + tags                                                  (status='approved')
  GH Actions cron, every 2 hours                      ── Stage 4 ──▶ Imgur upload
  Imgur OAuth: upload + gallery submit                                + posts row
  GH Actions cron, daily                              ── Stage 5 ──▶ analytics rows
                                                                     CSV artifact
```

`gallery.db` (SQLite) is the source of truth across all five stages.
Image bytes live on disk at `candidates/<hash>.<ext>` and
`enhanced/<hash>.jpg`; both folders are gitignored — only the DB is
committed.

## What it doesn't do

- It does not auto-approve. Stage 3 is human-in-the-loop.
- It does not run the model in your browser. The browser extension uses
  the same `Real-ESRGAN-x4plus.onnx` weights, but here we run inference
  via `onnxruntime` on the GH Actions runner (CPU).
- It does not handle Reddit OAuth. We use the public JSON listings, which
  is enough for top-of-day reads but Reddit may rate-limit if you turn
  the dial up.
- It does not bypass Imgur's gallery rules. Mature content is hard-coded
  off; titles must be ≥ 5 chars; per-account post throttling is theirs
  to enforce.

## Setup (local)

```bash
cd outreach/image-gallery
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt flask         # flask only needed for review_ui

python download_model.py                      # ~64 MB into models/
python db.py                                  # creates gallery.db

# Source-specific keys (only what you'll use)
export NASA_API_KEY=...                       # optional, DEMO_KEY works
export EXA_API_KEY=...                        # only for --exa

# Imgur (only needed for Stage 4 + 5)
export IMGUR_CLIENT_ID=...
export IMGUR_CLIENT_SECRET=...
export IMGUR_REFRESH_TOKEN=...
```

### Imgur OAuth one-time setup

1. Register an app at https://api.imgur.com/oauth2/addclient. Choose
   "OAuth 2 authorization with a callback URL" and use
   `https://ultrazoom.app/imgur-callback` (any URL works; Imgur just needs
   one).
2. Visit
   `https://api.imgur.com/oauth2/authorize?client_id=<CID>&response_type=token&state=manual`
   in a browser logged into the gallery account. Approve. The redirect
   URL contains `access_token=` and `refresh_token=` in the fragment.
3. Save the refresh token as `IMGUR_REFRESH_TOKEN` and the client id /
   secret as `IMGUR_CLIENT_ID` / `IMGUR_CLIENT_SECRET` in repo secrets.
4. Access tokens last 1 month; the refresh token is long-lived. The
   pipeline refreshes automatically.

## Run discovery + enhance

```bash
# All sources, default subreddits
python discover.py --reddit --commons --nasa --verbose

# Custom subreddit set
python discover.py --reddit --subreddit spaceporn --subreddit pics --verbose

# Enhance everything new
python enhance.py --verbose

# Or one-off a single candidate (e.g. after fiddling with watermark)
python enhance.py --candidate-id 42 --verbose
```

Re-running is idempotent on `(source, source_id)` and on image SHA-256.

## Run discovery + enhance in CI

`.github/workflows/image-gallery-discover.yml` runs daily at 13:00 UTC and
on `workflow_dispatch`. It commits `gallery.db` back to the branch and
uploads `enhanced/`, `candidates/`, and `gallery.db` as a workflow
artifact named `gallery-state-<run-id>` (14-day retention).

## Review

```bash
# Triage the local DB (defaults to ./gallery.db)
python review_ui.py

# Triage a CI artifact without overwriting your local DB
python review_ui.py --db ~/Downloads/gallery.db
```

Then open the URL the command prints (defaults to `http://127.0.0.1:5051`).

Keyboard shortcuts: `j`/`k` next/prev card · `v` approve & schedule ·
`x` reject · `e` edit title · `/` search · `?` help.

Workflow per card:
1. Glance at the original/enhanced compare. If the upscale didn't help
   (or made it worse), hit Reject.
2. Tighten the title to something gallery-readable. The default is
   whatever the source called it, which on Reddit is often
   "[OC] Sunset 6/7/2026 :)".
3. Drop in 3–5 lowercase tags. Imgur's tag UX is the main discovery vector.
4. Approve. The scheduler picks the next free slot in the
   10am-midnight ET window and writes `queue.scheduled_at`.
5. After your local review session, commit the updated `gallery.db` and
   push. The post workflow's cron picks up due rows on its next tick.

## Posting and analytics

Both run as GH Actions cron jobs by default. Stage 4 runs every 2 hours
and posts at most one item per tick (whose `scheduled_at <= now`).
Stage 5 runs once a day and snapshots `views`, `ups`, `downs`, `points`,
and `comment_count` for every post younger than `--max-age-days`
(default 60). Stage 5 also publishes a CSV artifact.

You can also drain the queue manually:

```bash
python post.py --verbose             # post one if due
python post.py --all-due --verbose   # drain everything due now
python post.py --dry-run             # plan a post without uploading
```

## Tuning knobs

- `config.py::DEFAULT_SUBREDDITS` — Reddit seed list.
- `config.py::REDDIT_MIN_SCORE` — min upvotes; defaults to 500.
- `config.py::POST_WINDOW_LOCAL_START_HOUR` / `_END_HOUR` /
  `POST_INTERVAL_HOURS` — when slots open. Default: 10am-midnight ET,
  every 2h = 8 slots/day.
- `config.py::IMGUR_MAX_BYTES` — Stage 2's compress-to-fit ceiling.
- `enhance.py::DEFAULT_TILE` / `DEFAULT_TILE_OVERLAP` — bigger tiles use
  more RAM but produce fewer seam artifacts.
- `config.py::WATERMARK_TEXT` — change the stamp.

## Files

```
outreach/image-gallery/
  README.md                     this file
  requirements.txt
  config.py                     paths, constants, env vars
  db.py                         SQLite schema + connect helper

  sources/
    base.py                     Candidate dataclass
    reddit.py                   public JSON listings
    commons.py                  POTD + NASA APOD
    exa.py                      Exa.ai semantic search

  discover.py                   Stage 1 CLI orchestrator
  enhance.py                    Stage 2: ONNX upscale + watermark + compress
  download_model.py             one-shot RealESRGAN downloader

  scheduler.py                  next-free-slot logic
  review_ui.py                  Stage 3 Flask UI (side-by-side compare)

  imgur.py                      thin Imgur API wrapper (OAuth refresh)
  post.py                       Stage 4: drain queue → post to Imgur
  analytics.py                  Stage 5: poll view/upvote stats

  candidates/                   downloaded sources (gitignored)
  enhanced/                     upscaled outputs (gitignored)
  posted/                       archive of what shipped (gitignored)
  models/                       ONNX weights cache (gitignored)
  gallery.db                    SQLite (committed; binary diff is small)

.github/workflows/
  image-gallery-discover.yml    daily Stage 1 + 2
  image-gallery-post.yml        every-2h Stage 4
  image-gallery-analytics.yml   daily Stage 5
```

## Operating principles

- Quality over volume. Better to post 4 visibly-improved upscales a day
  than 8 lossy ones — Imgur penalises low-engagement accounts.
- If a watermark looks intrusive on a card, fix the watermark — don't
  ship it half-broken.
- Every post links back to its source in the description. Treat that as
  non-negotiable, especially for Wikimedia and Reddit OC.
- If a source's content stops converting, prune it from
  `DEFAULT_SUBREDDITS`. Don't waste Stage 2 cycles on dead pipes.
