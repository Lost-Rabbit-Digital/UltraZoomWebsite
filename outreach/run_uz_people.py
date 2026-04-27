"""Ultra Zoom power-user outreach pipeline.

Independent from run_pipeline.py and run_hailbytes.py. Flow:

    Brave web search (seed + site:linkedin.com/in/)
      → Wiza individual reveal (LinkedIn URL → email + name + title)
      → email verify (Hunter / NeverBounce / ZeroBounce)
      → Claude personalized 2-sentence opener
      → append to "UltraZoom" tab of the source Sheet

Targets are individual power-users in image-heavy niches (vintage
resellers, genealogists, accessibility specialists, art appraisers,
forensic photographers, etc.) — they're the ones who feel the pain
Ultra Zoom solves, and a 100-user feedback cohort from this pool is
worth more than a thousand newsletter sign-ups.

Required env vars:
  BRAVE_SEARCH_API_KEY, WIZA_API_KEY, ANTHROPIC_API_KEY (HUNTER_API_KEY
  optional for verification fallback), GOOGLE_SHEET_ID + WIF for Sheets.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

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
from .enrich_wiza import lookup as wiza_lookup
from .stage_sheet import stage as stage_to_sheet
from .util import host_of, log, now_iso, today_iso

SEEDS_PATH = OUTREACH_DIR / "seeds_uz_people.txt"
PROMPT_PATH = PROMPTS_DIR / "uz_people_opener.md"
DEFAULT_PER_QUERY = 10
DEFAULT_MAX_STAGE = 25


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.run_uz_people")
    p.add_argument("--max-stage", type=int, default=DEFAULT_MAX_STAGE)
    p.add_argument("--per-query", type=int, default=DEFAULT_PER_QUERY)
    p.add_argument("--limit-seeds", type=int, default=8)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip email verification (useful when Wiza already returns verified emails).",
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


def _brave_people_search(
    *,
    api_key: str,
    query: str,
    num_results: int,
) -> list[dict[str, Any]]:
    """Brave web search restricted to LinkedIn profile pages via the
    site: operator. Brave doesn't have an Exa-style category=people
    mode, so we shape the query and filter the results.

    Asks for 2× num_results since site: queries leak in /posts/ and
    /pulse/ pages we'll discard before hitting the per-seed cap.
    """
    import urllib.error

    from . import discover_brave

    shaped = f"{query} site:linkedin.com/in/"
    try:
        items = discover_brave.search(
            api_key=api_key,
            seed=shaped,
            num_results=min(20, num_results * 2),
        )
    except urllib.error.HTTPError as e:
        log(f"  brave people error on {query[:60]}: HTTP {e.code}")
        return []
    out: list[dict[str, Any]] = []
    for it in items:
        url = it.get("url") or ""
        # Brave's site: operator doesn't constrain to /in/ alone, so
        # filter out company pages, posts, pulse articles, jobs, etc.
        if "linkedin.com/in/" not in url:
            continue
        text = it.get("description") or ""
        out.append(
            {
                "linkedin_url": url,
                "title": (it.get("title") or "").strip(),
                "summary": " ".join(text.split()).strip()[:600],
                "domain": host_of(url),
                "exa_score": None,
            }
        )
        if len(out) >= num_results:
            break
    return out


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
        if not cfg.brave_key:
            missing.append("BRAVE_SEARCH_API_KEY")
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
        f"max_stage={args.max_stage}  dry_run={args.dry_run} =="
    )

    raw: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for seed in seeds:
        if cfg.dry_run:
            log(f"  [dry] {seed}")
            continue
        items = _brave_people_search(
            api_key=cfg.brave_key or "",
            query=seed,
            num_results=args.per_query,
        )
        kept = 0
        for it in items:
            url = it["linkedin_url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            it["seed_used"] = seed
            it["bucket"] = "UZ"
            it["discovered_at"] = now_iso()
            it["source"] = "brave-people"
            raw.append(it)
            kept += 1
        log(f"  + [{kept}/{len(items)}]  {seed[:70]}")

    log(f"\ndiscovery: {len(raw)} unique LinkedIn profiles")

    enriched: list[dict[str, Any]] = []
    dropped = {"no_email": 0, "bad_email": 0, "manual_review": 0, "personalization": 0}
    for cand in raw:
        if len(enriched) >= args.max_stage:
            break
        if cfg.dry_run:
            cand.update(
                {
                    "editor_first_name": "Demo",
                    "editor_last_name": "User",
                    "editor_email": "demo@example.com",
                    "editor_title": cand.get("title", ""),
                    "hunter_confidence": 90,
                    "email_status": "valid",
                    "personalized_opener": f"[dry-run opener for {cand['linkedin_url']}]",
                    "lead_score": 60,
                    "domain": "linkedin.com",
                }
            )
            enriched.append(cand)
            continue

        contact = wiza_lookup(cand["linkedin_url"], api_key=cfg.wiza_key or "")
        if not contact or not contact.get("editor_email"):
            dropped["no_email"] += 1
            continue
        cand.update(contact)

        if not args.no_verify:
            try:
                verdict = email_verify(
                    contact["editor_email"],
                    hunter_key=cfg.hunter_key,
                    neverbounce_key=cfg.neverbounce_key,
                    zerobounce_key=cfg.zerobounce_key,
                )
            except Exception as e:  # noqa: BLE001
                log(f"  verify error for {contact['editor_email']}: {e}")
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
            log(f"  personalization rejected ({err}) for {cand['linkedin_url']}")
            dropped["personalization"] += 1
            continue

        cand["personalized_opener"] = opener
        cand["email_status"] = "valid"
        cand["lead_score"] = 60
        cand["notes"] = f"uz-people | {cand['linkedin_url']}"
        # Stage_sheet expects recent_post_url/title/description; map the
        # LinkedIn profile into those slots so the row remains useful in
        # the Sheet.
        cand["url"] = cand["linkedin_url"]
        cand["description"] = cand.get("summary", "")
        enriched.append(cand)
        log(f"  enriched: {cand['editor_email']}  ({cand['linkedin_url']})")

    appended = stage_to_sheet(cfg, enriched, dry_run=args.dry_run, tab=SHEET_TAB_UZ_PEOPLE)
    log(
        f"\ndone. raw={len(raw)} enriched={len(enriched)} appended={appended} "
        f"dropped={json.dumps(dropped)}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
