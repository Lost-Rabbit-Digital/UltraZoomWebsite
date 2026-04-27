"""Ultra Zoom power-user outreach pipeline.

Wiza-direct cold-email lane. Flow:

    plain-English seed
      → Claude translates to Wiza filter object (cached 7 days)
      → Wiza prospect_search preview (free; logs match count)
      → Wiza create_prospect_list (charges credits; max_profiles cap)
      → poll list until finished, fetch enriched contacts
      → optional Hunter / NeverBounce / ZeroBounce verify fallback
      → Claude personalized 2-sentence opener
      → append to "UltraZoom" tab of the source Sheet

Targets are individual power-users in image-heavy niches (vintage
resellers, genealogists, accessibility specialists, art appraisers,
forensic photographers, etc.) — they're the ones who feel the pain
Ultra Zoom solves, and a 100-user feedback cohort from this pool is
worth more than a thousand newsletter sign-ups.

Credit cost (partial enrichment): ~2 API email credits per returned
profile. Default max_profiles=5 keeps a single run under 10 credits;
crank it up via the workflow input once filter quality is verified.

Required env vars:
  WIZA_API_KEY, ANTHROPIC_API_KEY, GOOGLE_SHEET_ID + WIF for Sheets.
  Optional: HUNTER_API_KEY / NEVERBOUNCE_API_KEY / ZEROBOUNCE_API_KEY
  for the verification fallback (Wiza already pre-validates emails;
  these only run on rows segment=valid hasn't already cleared).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import discover_wiza, translate_filters
from .config import (
    DEFAULT_MODEL,
    OUTREACH_DIR,
    PROMPTS_DIR,
    SHEET_TAB_UZ_PEOPLE,
    Config,
    ensure_dirs,
)
from .enrich_personalize import MODEL_IDS, _call_anthropic
from .enrich_verify import verify as email_verify
from .stage_sheet import stage as stage_to_sheet
from .util import log, now_iso, today_iso

SEEDS_PATH = OUTREACH_DIR / "seeds_uz_people.txt"
PROMPT_PATH = PROMPTS_DIR / "uz_people_opener.md"
DEFAULT_LIMIT_SEEDS = 3
DEFAULT_MAX_PROFILES = 5


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.run_uz_people")
    p.add_argument(
        "--max-profiles",
        type=int,
        default=DEFAULT_MAX_PROFILES,
        help="Max enriched contacts per seed. Each one costs ~2 API email credits.",
    )
    p.add_argument(
        "--limit-seeds",
        type=int,
        default=DEFAULT_LIMIT_SEEDS,
        help="How many seeds to run this invocation (rotated daily).",
    )
    p.add_argument(
        "--enrichment-level",
        choices=["none", "partial", "full"],
        default="partial",
        help="Wiza enrichment level. 'none' = no email/phone (free).",
    )
    p.add_argument(
        "--preview-only",
        action="store_true",
        help="Hit /prospects/search (free) and log match counts; do not "
        "create a prospect list. Use this to validate filters before "
        "spending credits.",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip the post-Wiza email verifier. Wiza already returns "
        "segment=valid; the verifier is a belt-and-suspenders fallback.",
    )
    return p.parse_args(argv)


def _load_seeds(path: Path, *, limit: int) -> list[str]:
    seeds: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        seeds.append(line)
    import hashlib
    from datetime import datetime

    day = datetime.utcnow().date().toordinal()
    seeds.sort(key=lambda s: hashlib.md5(f"{day}|{s}".encode()).hexdigest())
    return seeds[:limit]


def _render_prompt(template: str, **fields: str) -> str:
    out = template
    for key, value in fields.items():
        out = out.replace("{" + key + "}", value or "")
    return out


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


def _personalize(
    *,
    candidate: dict[str, Any],
    niche: str,
    api_key: str,
    model: str,
) -> tuple[str, str]:
    template = PROMPT_PATH.read_text()
    prompt = _render_prompt(
        template,
        first_name=candidate.get("editor_first_name", ""),
        title=candidate.get("editor_title", "") or candidate.get("title", ""),
        niche=niche,
        summary=candidate.get("summary", ""),
    )
    raw = _call_anthropic(api_key, MODEL_IDS.get(model, MODEL_IDS["haiku"]), prompt, max_tokens=300)
    text = raw.strip().strip('"').strip("'")
    ok, reason = _validate_opener(text)
    if ok:
        return text, ""
    return "", reason


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()
    cfg = Config.from_env(dry_run=args.dry_run)

    if not cfg.dry_run:
        missing = []
        if not cfg.wiza_key:
            missing.append("WIZA_API_KEY")
        if not cfg.anthropic_key:
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            log(f"error: missing env vars: {', '.join(missing)}")
            return 1

    seeds = _load_seeds(SEEDS_PATH, limit=args.limit_seeds)
    log(
        f"== ultrazoom people outreach @ {today_iso()}  seeds={len(seeds)}  "
        f"max_profiles={args.max_profiles}  enrichment={args.enrichment_level}  "
        f"preview_only={args.preview_only}  dry_run={args.dry_run} =="
    )

    # Step 1: translate seeds to Wiza filter objects (cached 7d).
    seed_filters: list[tuple[str, dict[str, Any]]] = []
    for seed in seeds:
        if cfg.dry_run:
            log(f"  [dry] translate: {seed}")
            seed_filters.append((seed, {}))
            continue
        filters = translate_filters.translate(
            lane="uz",
            seed=seed,
            api_key=cfg.anthropic_key or "",
            model=args.model,
        )
        if not filters:
            log(f"  ! filter translation failed for: {seed[:70]}")
            continue
        log(f"  filter [{seed[:50]}]: {json.dumps(filters)[:160]}")
        seed_filters.append((seed, filters))

    # Step 2: preview (free) — gives us a sanity check on match counts
    # before we spend any credits. Always runs so the step summary has
    # something to show.
    previews: dict[str, int] = {}
    if not cfg.dry_run:
        for seed, filters in seed_filters:
            try:
                pv = discover_wiza.preview(
                    api_key=cfg.wiza_key or "",
                    filters=filters,
                    size=5,
                )
            except Exception as e:  # noqa: BLE001
                log(f"  preview error on {seed[:50]}: {e}")
                continue
            previews[seed] = pv["total"]
            log(f"  preview [{seed[:50]}]: {pv['total']} matches")

    if args.preview_only or cfg.dry_run:
        total = sum(previews.values())
        log(f"\npreview totals: {total} matches across {len(previews)} seeds")
        return 0

    # Step 3: create prospect list per seed and wait for enrichment.
    raw_contacts: list[dict[str, Any]] = []
    for seed, filters in seed_filters:
        if previews.get(seed, 0) == 0:
            log(f"  skipping (0 preview matches): {seed[:60]}")
            continue
        try:
            created = discover_wiza.create_list(
                api_key=cfg.wiza_key or "",
                name=f"UZ — {seed[:80]}",
                filters=filters,
                max_profiles=args.max_profiles,
                enrichment_level=args.enrichment_level,
            )
        except Exception as e:  # noqa: BLE001
            log(f"  create_list error on {seed[:50]}: {e}")
            continue
        list_data = created.get("data") or {}
        list_id = list_data.get("id") or list_data.get("uuid")
        if not list_id:
            log(f"  no list_id returned for {seed[:50]}: {created}")
            continue
        log(f"  list created id={list_id} for {seed[:50]}; polling...")

        status = discover_wiza.wait_for_list(api_key=cfg.wiza_key or "", list_id=list_id)
        if status not in discover_wiza.FINISHED_STATUSES:
            log(f"  list {list_id} ended in status={status}; skipping")
            continue

        contacts = discover_wiza.get_contacts(
            api_key=cfg.wiza_key or "",
            list_id=list_id,
            segment="valid",
        )
        log(f"  list {list_id}: {len(contacts)} valid contacts")
        for c in contacts:
            cand = discover_wiza.to_candidate(c, bucket="UZ", source="wiza-prospect")
            cand["seed_used"] = seed
            cand["discovered_at"] = now_iso()
            raw_contacts.append(cand)

    log(f"\ndiscovery: {len(raw_contacts)} enriched contacts across {len(seed_filters)} seeds")

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
                log(f"  verify error for {cand['editor_email']}: {e}")
                dropped["bad_email"] += 1
                continue
            if verdict == "invalid":
                dropped["bad_email"] += 1
                continue
            if verdict in {"risky", "unknown"}:
                dropped["manual_review"] += 1
                continue

        opener, err = _personalize(
            candidate=cand,
            niche=cand.get("seed_used", ""),
            api_key=cfg.anthropic_key or "",
            model=args.model,
        )
        if not opener:
            log(f"  personalization rejected ({err}) for {cand.get('editor_email')}")
            dropped["personalization"] += 1
            continue

        cand["personalized_opener"] = opener
        cand["lead_score"] = 60
        cand["notes"] = f"uz-people | {cand['linkedin_url']}"
        cand["url"] = cand["linkedin_url"]
        cand["description"] = cand.get("summary", "")
        enriched.append(cand)
        log(f"  enriched: {cand['editor_email']}  ({cand['linkedin_url']})")

    appended = stage_to_sheet(cfg, enriched, dry_run=args.dry_run, tab=SHEET_TAB_UZ_PEOPLE)
    log(
        f"\ndone. raw={len(raw_contacts)} enriched={len(enriched)} appended={appended} "
        f"dropped={json.dumps(dropped)}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
