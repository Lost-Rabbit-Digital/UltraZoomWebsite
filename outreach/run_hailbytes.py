"""HailBytes MSSP/pen-test outreach pipeline.

Apollo-direct cold-email lane. Flow:

    titles list (seeds_hb_titles.txt — decision-maker titles at MSSP /
      pen-test / offensive-security firms; signers, not ICs)
      → single Apollo /mixed_people/api_search filter
        {"person_titles": [<titles>],
         "contact_email_status": ["verified", "likely_to_engage"]}
      → preview (free; logs match count + per-filter strip diagnostic
        when 0)
      → Apollo paged search to ``max_profiles``, keeping verified emails
      → optional verifier fallback (Hunter / NeverBounce / ZeroBounce)
      → Claude personalized opener anchored to SAT or ASM (rotates daily;
        prompt links the recipient to hailbytes.com/sat or hailbytes.com/asm)
      → append to "HailBytes" tab of the source Sheet (MailMeteor reads
        from there to schedule sends inside Gmail)

No per-seed loop and no LLM filter translation: a single batched
people-search keeps the API surface honest and stops the per-seed
0-match cascade we hit when the LLM-generated filters were too narrow.

Dedupe is per-email against the HailBytes tab — domains aren't reused
across products, and the same firm could legitimately receive separate
SAT and ASM outreach. The MailMeteor template fills in the product
pitch + signature; the pipeline's job is to land a verified address +
two strong personalized sentences.

Required env vars:
  APOLLO_API_KEY, ANTHROPIC_API_KEY, GOOGLE_SHEET_ID + WIF for Sheets.
  Optional verifier keys: HUNTER_API_KEY / NEVERBOUNCE_API_KEY /
  ZEROBOUNCE_API_KEY.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import discover_apollo
from .config import (
    DEFAULT_MODEL,
    OUTREACH_DIR,
    PROMPTS_DIR,
    SHEET_TAB_HAILBYTES,
    Config,
    ensure_dirs,
)
from .enrich_personalize import MODEL_IDS, _call_anthropic
from .enrich_verify import verify as email_verify
from .stage_sheet import stage as stage_to_sheet
from .util import log, now_iso, today_iso

TITLES_PATH = OUTREACH_DIR / "seeds_hb_titles.txt"
PROMPT_PATH = PROMPTS_DIR / "hailbytes_opener.md"
DEFAULT_MAX_PROFILES = 100

PRODUCT_URLS = {
    "sat": "https://hailbytes.com/sat",
    "asm": "https://hailbytes.com/asm",
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.run_hailbytes")
    p.add_argument(
        "--max-profiles",
        type=int,
        default=DEFAULT_MAX_PROFILES,
        help="Max contacts pulled from Apollo for the title batch.",
    )
    p.add_argument(
        "--product",
        choices=["sat", "asm", "rotate"],
        default="rotate",
        help="Which HailBytes product the opener should set up. 'rotate' alternates daily.",
    )
    p.add_argument(
        "--preview-only",
        action="store_true",
        help="Hit Apollo /mixed_people/api_search at page 1 and log match counts; "
        "do not collect more pages.",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])
    p.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip the post-Apollo email verifier.",
    )
    return p.parse_args(argv)


def _load_titles(path: Path) -> list[str]:
    titles: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        titles.append(line)
    return titles


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


def _personalize_hailbytes(
    *,
    candidate: dict[str, Any],
    product: str,
    api_key: str,
    model: str,
) -> tuple[str, str]:
    template = PROMPT_PATH.read_text()
    prompt = _render_prompt(
        template,
        company=candidate.get("company") or candidate.get("domain", ""),
        domain=candidate.get("domain", ""),
        description=candidate.get("description", ""),
        title=candidate.get("editor_title", ""),
        product="HailBytes SAT" if product == "sat" else "HailBytes ASM (reNgine Cloud)",
        product_url=PRODUCT_URLS[product],
    )
    raw = _call_anthropic(api_key, MODEL_IDS.get(model, MODEL_IDS["haiku"]), prompt, max_tokens=300)
    text = raw.strip().strip('"').strip("'")
    ok, reason = _validate_opener(text)
    if ok:
        return text, ""
    return "", reason


def _pick_product(arg: str) -> str:
    if arg in {"sat", "asm"}:
        return arg
    from datetime import datetime

    return "sat" if datetime.utcnow().date().toordinal() % 2 == 0 else "asm"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()
    cfg = Config.from_env(dry_run=args.dry_run)

    if not cfg.dry_run:
        missing = []
        if not cfg.apollo_key:
            missing.append("APOLLO_API_KEY")
        if not cfg.anthropic_key:
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            log(f"error: missing env vars: {', '.join(missing)}")
            return 1

    product = _pick_product(args.product)
    titles = _load_titles(TITLES_PATH)
    if not titles:
        log(f"error: no titles loaded from {TITLES_PATH}")
        return 1

    filters: dict[str, Any] = {
        "person_titles": titles,
        "contact_email_status": ["verified", "likely_to_engage"],
    }
    log(
        f"== hailbytes outreach @ {today_iso()}  product={product}  "
        f"product_url={PRODUCT_URLS[product]}  titles={len(titles)}  "
        f"max_profiles={args.max_profiles}  preview_only={args.preview_only}  "
        f"dry_run={args.dry_run} =="
    )
    log(f"  filter: {json.dumps(filters)}")

    if cfg.dry_run:
        log("[dry] skipping Apollo + verify + personalize + stage")
        return 0

    # Step 1: preview (free).
    try:
        pv = discover_apollo.preview(api_key=cfg.apollo_key or "", filters=filters)
    except Exception as e:  # noqa: BLE001
        log(f"  preview error: {e}")
        return 1
    total = pv["total"]
    diag = pv.get("total_without_email_status")
    per_filter = pv.get("per_filter_strip") or {}
    if total == 0 and diag is not None:
        log(f"  preview: 0 matches (without contact_email_status filter: {diag})")
    else:
        log(f"  preview: {total} matches")
    if per_filter:
        strip_summary = ", ".join(
            f"-{k}={v}" for k, v in sorted(per_filter.items(), key=lambda kv: -kv[1])
        )
        log(f"    bottleneck strip: {strip_summary}")

    if args.preview_only:
        return 0
    if total == 0:
        log("  aborting: 0 preview matches, nothing to collect")
        return 0

    # Step 2: collect contacts.
    try:
        people = discover_apollo.collect(
            api_key=cfg.apollo_key or "",
            filters=filters,
            max_results=args.max_profiles,
        )
    except Exception as e:  # noqa: BLE001
        log(f"  collect error: {e}")
        return 1
    log(f"  collected {len(people)} from Apollo")

    raw_contacts: list[dict[str, Any]] = []
    for p in people:
        cand = discover_apollo.to_candidate(p, bucket="HB", source=f"apollo-{product}")
        cand["seed_used"] = cand.get("editor_title", "")
        cand["discovered_at"] = now_iso()
        raw_contacts.append(cand)

    log(f"\ndiscovery: {len(raw_contacts)} contacts")

    # Step 3: optional verify, then personalize.
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

        opener, err = _personalize_hailbytes(
            candidate=cand,
            product=product,
            api_key=cfg.anthropic_key or "",
            model=args.model,
        )
        if not opener:
            log(f"  personalization rejected ({err}) for {cand.get('editor_email')}")
            dropped["personalization"] += 1
            continue
        cand["personalized_opener"] = opener
        cand["lead_score"] = 70
        cand["notes"] = f"hb-{product} | {PRODUCT_URLS[product]}"
        cand["url"] = cand.get("linkedin_url") or cand.get("url", "")
        cand["description"] = cand.get("description", "")
        enriched.append(cand)
        log(f"  enriched: {cand['editor_email']}  ({cand.get('domain', '')}, {product})")

    appended = stage_to_sheet(cfg, enriched, dry_run=args.dry_run, tab=SHEET_TAB_HAILBYTES)
    log(
        f"\ndone. raw={len(raw_contacts)} enriched={len(enriched)} appended={appended} "
        f"dropped={json.dumps(dropped)}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
