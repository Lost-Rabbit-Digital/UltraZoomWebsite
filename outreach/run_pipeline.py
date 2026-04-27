"""CLI orchestrator for the outreach pipeline.

Single entry point. Common flags:

    --max-stage <n>    cap how many qualified candidates get enriched and staged
    --bucket <A|B|C|D> override the seed-bucket rotation
    --discover-only    fill state files, skip enrich and stage
    --retry-failed     re-run personalization for previously failed candidates
    --dry-run          log every action, write nothing external
    --model <id>       claude model alias (haiku, sonnet, opus)

See README.md for the end-to-end flow and MailMeteor template setup.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import (
    DEFAULT_MAX_STAGE,
    DEFAULT_MODEL,
    DEFAULT_PER_QUERY,
    DROPPED_DIR,
    Config,
    ensure_dirs,
)
from .discover import run as run_discovery
from .enrich_hunter import lookup as hunter_lookup
from .enrich_personalize import personalize as claude_personalize
from .enrich_verify import verify as email_verify
from .qualify import qualify
from .seeds import select_for_run
from .stage_sheet import stage as stage_to_sheet
from .state import load_seen, save_seen
from .util import log, now_iso, today_iso

DROPPED_LOG = DROPPED_DIR / "dropped.jsonl"
RETRY_QUEUE = DROPPED_DIR / "personalization_failures.jsonl"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.run_pipeline")
    p.add_argument("--max-stage", type=int, default=DEFAULT_MAX_STAGE)
    p.add_argument("--bucket", choices=["A", "B", "C", "D"], default=None)
    p.add_argument("--per-query", type=int, default=DEFAULT_PER_QUERY)
    p.add_argument("--discover-only", action="store_true")
    p.add_argument("--retry-failed", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])
    p.add_argument("--no-rss", action="store_true")
    p.add_argument(
        "--no-reachability",
        action="store_true",
        help="skip the HTTP reachability probe in qualify (useful for offline dry runs)",
    )
    return p.parse_args(argv)


def _check_keys(cfg: Config, *, mode: str) -> None:
    """Fail fast when required keys are missing for the requested mode."""
    if cfg.dry_run:
        return
    needed: list[str] = []
    if mode in {"discover", "full"}:
        if not cfg.brave_key and not cfg.exa_key:
            needed.append("BRAVE_SEARCH_API_KEY or EXA_API_KEY (need at least one)")
    if mode == "full":
        if not cfg.hunter_key:
            # Hunter is now used both for domain search and (by default)
            # for email verification, so it's a single hard requirement.
            needed.append("HUNTER_API_KEY")
        if not cfg.anthropic_key:
            needed.append("ANTHROPIC_API_KEY")
        if not cfg.google_service_account_json:
            needed.append("GOOGLE_SERVICE_ACCOUNT_JSON")
    if needed:
        log("error: missing required env vars:")
        for n in needed:
            log(f"  - {n}")
        log("re-run with --dry-run to preview without secrets")
        sys.exit(1)


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
        # Persist enough state to retry later via --retry-failed.
        with RETRY_QUEUE.open("a") as f:
            f.write(json.dumps(candidate) + "\n")


def _enrich_one(
    cfg: Config, candidate: dict[str, Any], *, model: str
) -> tuple[dict[str, Any] | None, str]:
    """Run Hunter → verify → Claude on one qualified candidate. Returns
    ``(enriched, drop_status)`` — exactly one is non-empty.
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

    # Hunter.
    domain = candidate.get("domain") or ""
    try:
        hunter = hunter_lookup(domain, api_key=cfg.hunter_key or "")
    except Exception as e:  # noqa: BLE001
        log(f"  hunter error for {domain}: {e}")
        return None, "no_editor_found"
    if not hunter or not hunter.get("editor_email"):
        return None, "no_editor_found"

    # Verify. Hunter is the default; NeverBounce/ZeroBounce override
    # when configured (they catch a few catch-all cases Hunter misses).
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

    # Claude personalization.
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


def _retry_failed(cfg: Config, model: str, max_stage: int) -> list[dict[str, Any]]:
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
    for candidate in pending:
        if len(enriched) >= max_stage:
            still_failed.append(candidate)
            continue
        result, drop = _enrich_one(cfg, candidate, model=model)
        if result:
            enriched.append(result)
        else:
            if drop == "personalization_failed":
                still_failed.append(candidate)
            else:
                _record_drop(candidate, drop, "retry: drop")
    # Replace queue with whatever still hasn't succeeded.
    if still_failed:
        RETRY_QUEUE.write_text("\n".join(json.dumps(c) for c in still_failed) + "\n")
    else:
        RETRY_QUEUE.unlink(missing_ok=True)
    return enriched


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()
    cfg = Config.from_env(dry_run=args.dry_run)

    mode = "full"
    if args.discover_only:
        mode = "discover"
    if args.retry_failed:
        mode = "full"
    _check_keys(cfg, mode=mode)

    log(
        f"== outreach pipeline @ {today_iso()}  bucket={args.bucket or 'rotate'}  "
        f"max_stage={args.max_stage}  dry_run={args.dry_run} =="
    )

    if args.retry_failed:
        enriched = _retry_failed(cfg, args.model, args.max_stage)
        appended = stage_to_sheet(cfg, enriched, dry_run=args.dry_run)
        log(f"retry-failed done: enriched={len(enriched)} appended={appended}")
        return 0

    selection = select_for_run(bucket=args.bucket, persist=not args.dry_run)
    log(f"seed bucket: {selection.bucket}  seeds: {len(selection.seeds)}")

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
    # Persist seen-state immediately, even before enrichment, so a crash
    # mid-enrichment doesn't cause us to re-discover the same URLs
    # tomorrow.
    if not args.dry_run:
        save_seen(seen_urls, seen_domains)

    if args.discover_only:
        log(f"discover-only: {len(qualified)} qualified, state saved")
        return 0

    # Enrich qualified candidates in lead_score order until we've
    # produced max_stage successful ones.
    qualified.sort(key=lambda c: -c.get("lead_score", 0))
    enriched: list[dict[str, Any]] = []
    for candidate in qualified:
        if len(enriched) >= args.max_stage:
            break
        result, drop = _enrich_one(cfg, candidate, model=args.model)
        if result:
            enriched.append(result)
            log(
                f"  enriched: {result.get('editor_email')} "
                f"({candidate.get('domain')}, score {candidate.get('lead_score')})"
            )
        else:
            log(f"  dropped: {candidate.get('domain')} — {drop}")
            _record_drop(candidate, drop, "")

    appended = stage_to_sheet(cfg, enriched, dry_run=args.dry_run)
    log(
        f"\ndone. raw={len(raw)} qualified={q_stats['qualified']} "
        f"enriched={len(enriched)} appended={appended}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
