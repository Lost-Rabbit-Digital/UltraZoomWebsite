"""Ultra Zoom outreach pipeline.

One CLI for two complementary cold-email lanes that both write to the
``UltraZoom`` tab MailMeteor reads from:

  --mode content    Brave/Exa/RSS → Hunter editor → verify → Claude opener
                    Targets editors of roundup articles, accessibility
                    blogs, genealogy publications. Best at finding the
                    person who *writes about* image-heavy tools.
  --mode prospects  Apollo people-search → verify → Claude opener
                    Targets B2B power-users at companies whose staff
                    routinely review lots of detailed photos / scans /
                    screenshots in a browser (radiology, insurance
                    claims, real-estate appraisal, manufacturing QA,
                    auction houses, GIS, genealogy, etc. — see
                    seeds_uz_companies.txt).
  --mode both       (default) content first, then prospects.

Default seed bucket for content is **E (genealogy)** — Ultra Zoom's
strongest customer-pain fit, which family-history researchers feel daily
on faded census records and scanned newspapers. Override with --bucket.

Required env vars (live runs):
  Content path:  BRAVE_SEARCH_API_KEY or EXA_API_KEY, HUNTER_API_KEY,
                 ANTHROPIC_API_KEY
  Prospects:     APOLLO_API_KEY, ANTHROPIC_API_KEY
  Both:          GOOGLE_SHEET_ID + Google Sheets ADC/WIF auth

Optional verifiers: NEVERBOUNCE_API_KEY, ZEROBOUNCE_API_KEY (override
Hunter when set).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from . import discover_apollo, translate_filters
from .config import (
    DEFAULT_MAX_STAGE,
    DEFAULT_MODEL,
    DEFAULT_PER_QUERY,
    DROPPED_DIR,
    OUTREACH_DIR,
    PROMPTS_DIR,
    SHEET_TAB_UZ_PEOPLE,
    Config,
    ensure_dirs,
)
from .discover import run as run_discovery
from .enrich_hunter import lookup as hunter_lookup
from .enrich_personalize import MODEL_IDS, _call_anthropic
from .enrich_personalize import personalize as claude_personalize
from .enrich_verify import verify as email_verify
from .qualify import qualify
from .seeds import select_for_run
from .stage_sheet import stage as stage_to_sheet
from .state import load_seen, save_seen
from .util import log, now_iso, today_iso

UZ_COMPANY_SEEDS = OUTREACH_DIR / "seeds_uz_companies.txt"
UZ_PEOPLE_OPENER = PROMPTS_DIR / "uz_people_opener.md"
DROPPED_LOG = DROPPED_DIR / "dropped.jsonl"
RETRY_QUEUE = DROPPED_DIR / "personalization_failures.jsonl"

# Default bucket for content mode. Genealogy is UZ's strongest customer
# fit — squinting at census records and scanned newspapers is the daily
# pain Ultra Zoom solves. Override on the CLI / workflow input.
DEFAULT_CONTENT_BUCKET = "E"
DEFAULT_PROSPECTS_LIMIT_SEEDS = 5
DEFAULT_PROSPECTS_MAX_PROFILES = 25


# ---------------------------------------------------------------------------
# Content path
# ---------------------------------------------------------------------------


def _record_drop(candidate: dict[str, Any], status: str, reason: str) -> None:
    DROPPED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "logged_at": now_iso(),
        "status": status,
        "reason": reason,
        "url": candidate.get("url"),
        "domain": candidate.get("domain"),
        "title": candidate.get("title"),
        "lead_score": candidate.get("lead_score"),
        "source": candidate.get("source"),
        "seed_used": candidate.get("seed_used"),
    }
    with DROPPED_LOG.open("a") as f:
        f.write(json.dumps(payload) + "\n")
    if status == "personalization_failed":
        with RETRY_QUEUE.open("a") as f:
            f.write(json.dumps(candidate) + "\n")


def _enrich_content_one(
    cfg: Config, candidate: dict[str, Any], *, model: str
) -> tuple[dict[str, Any] | None, str]:
    """Hunter → verify → Claude on one qualified content lead.
    Returns ``(enriched, drop_status)`` — exactly one is non-empty.
    """
    if cfg.dry_run:
        out = dict(candidate)
        out.update(
            {
                "editor_first_name": "Demo",
                "editor_last_name": "Editor",
                "editor_email": f"demo@{candidate.get('domain', 'example.com')}",
                "hunter_confidence": 90,
                "email_status": "valid",
                "personalized_opener": "[dry-run opener]",
                "discovered_at": candidate.get("discovered_at", now_iso()),
            }
        )
        return out, ""

    domain = candidate.get("domain") or ""
    try:
        hunter = hunter_lookup(domain, api_key=cfg.hunter_key or "")
    except Exception as e:  # noqa: BLE001
        log(f"  hunter error for {domain}: {e}")
        return None, "no_editor_found"
    if not hunter or not hunter.get("editor_email"):
        return None, "no_editor_found"

    try:
        verdict = email_verify(
            hunter["editor_email"],
            hunter_key=cfg.hunter_key,
            neverbounce_key=cfg.neverbounce_key,
            zerobounce_key=cfg.zerobounce_key,
        )
    except Exception as e:  # noqa: BLE001
        log(f"  verify error for {hunter['editor_email']}: {e}")
        return None, "verify_error"
    if verdict == "invalid":
        return None, "bad_email"
    if verdict in {"risky", "unknown"}:
        return None, "manual_review"

    try:
        opener, err = claude_personalize(candidate, api_key=cfg.anthropic_key or "", model=model)
    except Exception as e:  # noqa: BLE001
        log(f"  claude error for {domain}: {e}")
        return None, "personalization_failed"
    if not opener:
        log(f"  personalization rejected ({err}) for {domain}")
        return None, "personalization_failed"

    enriched = dict(candidate)
    enriched.update(hunter)
    enriched["email_status"] = "valid"
    enriched["personalized_opener"] = opener
    return enriched, ""


def _retry_failed_content(cfg: Config, model: str, max_stage: int) -> list[dict[str, Any]]:
    if not RETRY_QUEUE.exists():
        log("retry: no personalization_failures.jsonl, nothing to retry")
        return []
    pending: list[dict[str, Any]] = []
    for line in RETRY_QUEUE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            pending.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    log(f"retry: {len(pending)} previously failed candidates")

    enriched: list[dict[str, Any]] = []
    still_failed: list[dict[str, Any]] = []
    for cand in pending:
        if len(enriched) >= max_stage:
            still_failed.append(cand)
            continue
        result, drop = _enrich_content_one(cfg, cand, model=model)
        if result:
            enriched.append(result)
        elif drop == "personalization_failed":
            still_failed.append(cand)
        else:
            _record_drop(cand, drop, "retry: drop")
    if still_failed:
        RETRY_QUEUE.write_text("\n".join(json.dumps(c) for c in still_failed) + "\n")
    else:
        RETRY_QUEUE.unlink(missing_ok=True)
    return enriched


def _run_content(cfg: Config, args: argparse.Namespace) -> int:
    """Discover → qualify → enrich → stage. Writes to the UltraZoom tab."""
    if args.retry_failed:
        enriched = _retry_failed_content(cfg, args.model, args.content_max_stage)
        appended = stage_to_sheet(cfg, enriched, dry_run=cfg.dry_run, tab=SHEET_TAB_UZ_PEOPLE)
        log(f"content retry: enriched={len(enriched)} appended={appended}")
        return appended

    selection = select_for_run(bucket=args.bucket, persist=not cfg.dry_run)
    log(f"  bucket={selection.bucket}  seeds={len(selection.seeds)}")

    raw = run_discovery(
        cfg,
        selection,
        per_query=args.per_query,
        use_rss=not args.no_rss,
    )

    seen_urls, seen_domains = load_seen()
    qualified, q_stats = qualify(
        raw,
        seen_urls=seen_urls,
        seen_domains=seen_domains,
        reachability_check=not args.no_reachability,
    )
    if not cfg.dry_run:
        save_seen(seen_urls, seen_domains)

    if args.discover_only:
        log(f"discover-only: {len(qualified)} qualified, state saved")
        return 0

    qualified.sort(key=lambda c: -c.get("lead_score", 0))
    enriched: list[dict[str, Any]] = []
    for cand in qualified:
        if len(enriched) >= args.content_max_stage:
            break
        result, drop = _enrich_content_one(cfg, cand, model=args.model)
        if result:
            enriched.append(result)
            log(
                f"  enriched: {result.get('editor_email')} "
                f"({cand.get('domain')}, score {cand.get('lead_score')})"
            )
        else:
            log(f"  dropped: {cand.get('domain')} — {drop}")
            _record_drop(cand, drop, "")

    appended = stage_to_sheet(cfg, enriched, dry_run=cfg.dry_run, tab=SHEET_TAB_UZ_PEOPLE)
    log(
        f"content done. raw={len(raw)} qualified={q_stats['qualified']} "
        f"enriched={len(enriched)} appended={appended}"
    )
    return appended


# ---------------------------------------------------------------------------
# Prospects path
# ---------------------------------------------------------------------------


def _load_prospects_seeds(path: Path, *, limit: int) -> list[str]:
    seeds: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        seeds.append(line)
    day = datetime.utcnow().date().toordinal()
    seeds.sort(key=lambda s: hashlib.md5(f"{day}|{s}".encode()).hexdigest())
    return seeds[:limit]


def _validate_opener(text: str) -> tuple[bool, str]:
    if not text:
        return False, "empty"
    if "—" in text or "–" in text:
        return False, "em dash"
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s for s in sentences if s.strip()]
    if len(sentences) < 1 or len(sentences) > 3:
        return False, f"sentence count ({len(sentences)})"
    if len(text.split()) > 60:
        return False, f"too long ({len(text.split())} words)"
    return True, ""


def _personalize_prospects(
    *,
    candidate: dict[str, Any],
    api_key: str,
    model: str,
) -> tuple[str, str]:
    template = UZ_PEOPLE_OPENER.read_text()
    prompt = (
        template.replace("{first_name}", candidate.get("editor_first_name", ""))
        .replace("{title}", candidate.get("editor_title", "") or candidate.get("title", ""))
        .replace("{niche}", candidate.get("seed_used", ""))
        .replace("{summary}", candidate.get("summary", ""))
        .replace("{company}", candidate.get("company") or candidate.get("domain", ""))
    )
    raw = _call_anthropic(api_key, MODEL_IDS.get(model, MODEL_IDS["haiku"]), prompt, max_tokens=300)
    text = raw.strip().strip('"').strip("'")
    ok, reason = _validate_opener(text)
    if ok:
        return text, ""
    return "", reason


def _run_prospects(cfg: Config, args: argparse.Namespace) -> int:
    """Apollo filter → preview → collect → verify → personalize → stage to
    UltraZoom tab.
    """
    seeds = _load_prospects_seeds(UZ_COMPANY_SEEDS, limit=args.prospects_limit_seeds)
    log(f"  seeds={len(seeds)}  max_profiles={args.prospects_max_profiles}  "
        f"preview_only={args.preview_only}")

    # Step 1: translate seeds to Apollo filter objects (cached 7d).
    seed_filters: list[tuple[str, dict[str, Any]]] = []
    for seed in seeds:
        if cfg.dry_run:
            log(f"  [dry] translate: {seed[:80]}")
            seed_filters.append((seed, {}))
            continue
        filters = translate_filters.translate(
            lane="uz",
            seed=seed,
            api_key=cfg.anthropic_key or "",
            model=args.model,
        )
        if not filters:
            log(f"  ! filter translation failed: {seed[:70]}")
            continue
        log(f"  filter [{seed[:50]}]: {json.dumps(filters)[:160]}")
        seed_filters.append((seed, filters))

    # Step 2: preview (free) — sanity-check match counts before pulling more.
    previews: dict[str, int] = {}
    if not cfg.dry_run:
        for seed, filters in seed_filters:
            try:
                pv = discover_apollo.preview(api_key=cfg.apollo_key or "", filters=filters)
            except Exception as e:  # noqa: BLE001
                log(f"  preview error on {seed[:50]}: {e}")
                continue
            previews[seed] = pv["total"]
            diag = pv.get("total_without_email_status")
            if pv["total"] == 0 and diag is not None:
                log(
                    f"  preview [{seed[:50]}]: 0 matches "
                    f"(without contact_email_status filter: {diag})"
                )
            else:
                log(f"  preview [{seed[:50]}]: {pv['total']} matches")

    if args.preview_only or cfg.dry_run:
        total = sum(previews.values())
        log(f"\nprospects preview: {total} matches across {len(previews)} seeds")
        return 0

    # Step 3: collect contacts per seed.
    raw_contacts: list[dict[str, Any]] = []
    for seed, filters in seed_filters:
        if previews.get(seed, 0) == 0:
            log(f"  skipping (0 preview): {seed[:60]}")
            continue
        try:
            people = discover_apollo.collect(
                api_key=cfg.apollo_key or "",
                filters=filters,
                max_results=args.prospects_max_profiles,
            )
        except Exception as e:  # noqa: BLE001
            log(f"  collect error on {seed[:50]}: {e}")
            continue
        log(f"  collected {len(people)} for {seed[:60]}")
        for p in people:
            cand = discover_apollo.to_candidate(p, bucket="UZ", source="apollo-prospect")
            cand["seed_used"] = seed
            cand["discovered_at"] = now_iso()
            raw_contacts.append(cand)

    log(f"\nprospects discovery: {len(raw_contacts)} contacts across {len(seed_filters)} seeds")

    # Step 4: optional verify, then personalize.
    enriched: list[dict[str, Any]] = []
    dropped = {"no_email": 0, "bad_email": 0, "manual_review": 0, "personalization": 0}
    for cand in raw_contacts:
        if not cand.get("editor_email"):
            dropped["no_email"] += 1
            continue
        if not args.no_verify:
            try:
                verdict = email_verify(
                    cand["editor_email"],
                    hunter_key=cfg.hunter_key,
                    neverbounce_key=cfg.neverbounce_key,
                    zerobounce_key=cfg.zerobounce_key,
                )
            except Exception as e:  # noqa: BLE001
                log(f"  verify error {cand['editor_email']}: {e}")
                dropped["bad_email"] += 1
                continue
            if verdict == "invalid":
                dropped["bad_email"] += 1
                continue
            if verdict in {"risky", "unknown"}:
                dropped["manual_review"] += 1
                continue

        opener, err = _personalize_prospects(
            candidate=cand, api_key=cfg.anthropic_key or "", model=args.model
        )
        if not opener:
            log(f"  personalization rejected ({err}) for {cand.get('editor_email')}")
            dropped["personalization"] += 1
            continue

        cand["personalized_opener"] = opener
        cand["lead_score"] = 60
        cand["notes"] = f"uz-prospects | {cand.get('linkedin_url', '')}"
        cand["url"] = cand.get("linkedin_url") or ""
        cand["description"] = cand.get("summary", "")
        enriched.append(cand)
        log(f"  enriched: {cand['editor_email']}  ({cand.get('linkedin_url', '')})")

    appended = stage_to_sheet(cfg, enriched, dry_run=cfg.dry_run, tab=SHEET_TAB_UZ_PEOPLE)
    log(
        f"prospects done. raw={len(raw_contacts)} enriched={len(enriched)} "
        f"appended={appended} dropped={json.dumps(dropped)}"
    )
    return appended


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _check_keys(cfg: Config, *, mode: str) -> list[str]:
    if cfg.dry_run:
        return []
    needed: list[str] = []
    if mode in {"content", "both"}:
        if not cfg.brave_key and not cfg.exa_key:
            needed.append("BRAVE_SEARCH_API_KEY or EXA_API_KEY")
        if not cfg.hunter_key:
            needed.append("HUNTER_API_KEY")
        if not cfg.anthropic_key:
            needed.append("ANTHROPIC_API_KEY")
    if mode in {"prospects", "both"}:
        if not cfg.apollo_key:
            needed.append("APOLLO_API_KEY")
        if not cfg.anthropic_key and "ANTHROPIC_API_KEY" not in needed:
            needed.append("ANTHROPIC_API_KEY")
    return needed


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.run_ultrazoom")
    p.add_argument(
        "--mode",
        choices=["content", "prospects", "both"],
        default="both",
        help="content = Brave/Exa/RSS → Hunter editor; prospects = Apollo "
        "B2B people; both = run content then prospects.",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])

    # Content-mode knobs.
    p.add_argument(
        "--bucket",
        choices=["A", "B", "C", "D", "E", "F"],
        default=DEFAULT_CONTENT_BUCKET,
        help=f"Seed bucket for content mode. Default: {DEFAULT_CONTENT_BUCKET} (genealogy).",
    )
    p.add_argument("--content-max-stage", type=int, default=DEFAULT_MAX_STAGE)
    p.add_argument("--per-query", type=int, default=DEFAULT_PER_QUERY)
    p.add_argument("--no-rss", action="store_true")
    p.add_argument(
        "--no-reachability",
        action="store_true",
        help="Skip qualify's HTTP reachability probe (offline dry runs).",
    )
    p.add_argument(
        "--discover-only",
        action="store_true",
        help="Content mode: populate state, skip enrich + stage.",
    )
    p.add_argument(
        "--retry-failed",
        action="store_true",
        help="Content mode: re-run personalization for "
        "personalization_failures.jsonl candidates.",
    )

    # Prospects-mode knobs.
    p.add_argument(
        "--prospects-limit-seeds",
        type=int,
        default=DEFAULT_PROSPECTS_LIMIT_SEEDS,
        help=f"Seeds to run from seeds_uz_companies.txt. Default: {DEFAULT_PROSPECTS_LIMIT_SEEDS}.",
    )
    p.add_argument(
        "--prospects-max-profiles",
        type=int,
        default=DEFAULT_PROSPECTS_MAX_PROFILES,
        help="Max enriched contacts per seed pulled from Apollo. "
        f"Default: {DEFAULT_PROSPECTS_MAX_PROFILES}.",
    )
    p.add_argument(
        "--preview-only",
        action="store_true",
        help="Prospects mode: hit Apollo /mixed_people/api_search at page 1 and stop.",
    )
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="Prospects mode: skip the post-Apollo verifier fallback.",
    )

    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()
    cfg = Config.from_env(dry_run=args.dry_run)

    missing = _check_keys(cfg, mode=args.mode)
    if missing:
        log("error: missing env vars:")
        for n in missing:
            log(f"  - {n}")
        return 1

    log(
        f"== Ultra Zoom outreach @ {today_iso()}  mode={args.mode}  "
        f"dry_run={args.dry_run} =="
    )

    appended_total = 0
    if args.mode in {"content", "both"}:
        log("\n-- content path --")
        try:
            appended_total += _run_content(cfg, args)
        except Exception as e:  # noqa: BLE001
            log(f"content path error: {e}")

    if args.mode in {"prospects", "both"}:
        log("\n-- prospects path --")
        try:
            appended_total += _run_prospects(cfg, args)
        except Exception as e:  # noqa: BLE001
            log(f"prospects path error: {e}")

    log(f"\n=== Ultra Zoom run complete. appended={appended_total} ===")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
