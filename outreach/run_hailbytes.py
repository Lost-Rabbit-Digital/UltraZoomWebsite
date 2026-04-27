"""HailBytes MSSP/pentest outreach pipeline.

Independent from the listicle pipeline (run_pipeline.py) so the two
lanes can run on separate schedules without sharing state. Flow:

    Exa /search (category="company")
      → Hunter domain search (decision-maker title priority)
      → email verify (Hunter / NeverBounce / ZeroBounce)
      → Claude personalized opener (2 sentences in David's voice)
      → append to "HailBytes" tab of the source Sheet

Dedupe is per-email against the HailBytes tab — domains aren't reused
across products, and the same firm could legitimately receive separate
SAT and ASM outreach. The MailMeteor template fills in the product
pitch + signature; the pipeline's job is to land a verified address +
two strong personalized sentences.

Required env vars (set as repo Secrets / Variables):
  EXA_API_KEY, HUNTER_API_KEY, ANTHROPIC_API_KEY, WIZA_API_KEY (optional fallback)
  GOOGLE_SHEET_ID + Workload Identity Federation for Sheets access
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from . import discover_exa
from .config import (
    DEFAULT_MODEL,
    OUTREACH_DIR,
    PROMPTS_DIR,
    SHEET_TAB_HAILBYTES,
    Config,
    ensure_dirs,
)
from .enrich_hunter import lookup as hunter_lookup
from .enrich_personalize import MODEL_IDS, _call_anthropic
from .enrich_verify import verify as email_verify
from .stage_sheet import stage as stage_to_sheet
from .util import host_of, log, now_iso, today_iso

SEEDS_PATH = OUTREACH_DIR / "seeds_hb_mssp.txt"
PROMPT_PATH = PROMPTS_DIR / "hailbytes_opener.md"
DEFAULT_PER_QUERY = 10
DEFAULT_MAX_STAGE = 25

# Title priority specific to HailBytes prospects. Earlier index wins.
HB_ROLE_TIERS: list[tuple[str, list[str]]] = [
    ("ciso", ["ciso", "chief information security officer", "chief security officer"]),
    ("cto", ["cto", "chief technology officer"]),
    ("offensive", ["offensive security", "red team", "head of red team", "principal consultant"]),
    ("security_analyst", ["security analyst", "security engineer", "security operations"]),
    ("systems_analyst", ["systems analyst", "systems engineer", "infrastructure engineer"]),
    ("director", ["director of services", "director of consulting", "director of security"]),
    ("founder", ["founder", "co-founder", "ceo", "principal", "owner"]),
]
GENERIC_INBOXES = {
    "info",
    "sales",
    "contact",
    "hello",
    "support",
    "help",
    "team",
    "admin",
    "marketing",
    "press",
}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.run_hailbytes")
    p.add_argument("--max-stage", type=int, default=DEFAULT_MAX_STAGE)
    p.add_argument("--per-query", type=int, default=DEFAULT_PER_QUERY)
    p.add_argument(
        "--product",
        choices=["sat", "asm", "rotate"],
        default="rotate",
        help="Which HailBytes product the opener should set up. 'rotate' alternates daily.",
    )
    p.add_argument("--limit-seeds", type=int, default=10, help="Max seed queries per run.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])
    return p.parse_args(argv)


def _load_seeds(path: Path, *, limit: int) -> list[str]:
    seeds: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        seeds.append(line)
    # Daily rotation: deterministic shuffle by day-of-year so we don't
    # always hit the same first N queries.
    import hashlib
    from datetime import datetime

    day = datetime.utcnow().date().toordinal()
    seeds.sort(key=lambda s: hashlib.md5(f"{day}|{s}".encode()).hexdigest())
    return seeds[:limit]


def _hb_tier(person: dict[str, Any]) -> int:
    haystack = " ".join(
        [
            (person.get("position") or "").lower(),
            (person.get("department") or "").lower(),
            (person.get("seniority") or "").lower(),
        ]
    )
    for idx, (_, keywords) in enumerate(HB_ROLE_TIERS):
        if any(k in haystack for k in keywords):
            return idx
    return len(HB_ROLE_TIERS)


def _is_generic(email: str) -> bool:
    local = (email or "").split("@", 1)[0].lower()
    return local in GENERIC_INBOXES


def _hunter_with_hb_priority(domain: str, *, api_key: str) -> dict[str, Any] | None:
    """Same as enrich_hunter.lookup but ranks people by HailBytes-specific
    title tiers and skips generic info@/sales@ inboxes.
    """
    import urllib.error
    import urllib.parse

    from .cache import JsonCache
    from .config import HUNTER_CACHE, HUNTER_TTL_DAYS
    from .enrich_hunter import _call

    cache = JsonCache(HUNTER_CACHE, ttl_days=HUNTER_TTL_DAYS)
    cache_key = f"hb|{domain}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    try:
        json_resp = _call(
            "/domain-search",
            {"domain": domain, "api_key": api_key, "limit": "10"},
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            cache.set(cache_key, {})
            return None
        raise

    emails = ((json_resp.get("data") or {}).get("emails")) or []
    candidates = [e for e in emails if e.get("value") and not _is_generic(e["value"])]
    if not candidates:
        cache.set(cache_key, {})
        return None

    candidates.sort(key=lambda p: (_hb_tier(p), -int(p.get("confidence") or 0)))
    pick = candidates[0]
    result = {
        "editor_first_name": pick.get("first_name") or "",
        "editor_last_name": pick.get("last_name") or "",
        "editor_email": pick.get("value"),
        "editor_title": pick.get("position") or "",
        "hunter_confidence": int(pick.get("confidence") or 0),
    }
    cache.set(cache_key, result)
    return result


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
    # Daily rotation: alternate by ordinal day.
    from datetime import datetime

    return "sat" if datetime.utcnow().date().toordinal() % 2 == 0 else "asm"


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()
    cfg = Config.from_env(dry_run=args.dry_run)

    if not cfg.dry_run:
        missing = []
        if not cfg.exa_key:
            missing.append("EXA_API_KEY")
        if not cfg.hunter_key:
            missing.append("HUNTER_API_KEY")
        if not cfg.anthropic_key:
            missing.append("ANTHROPIC_API_KEY")
        if missing:
            log(f"error: missing env vars: {', '.join(missing)}")
            return 1

    product = _pick_product(args.product)
    seeds = _load_seeds(SEEDS_PATH, limit=args.limit_seeds)
    log(
        f"== hailbytes outreach @ {today_iso()}  product={product}  "
        f"seeds={len(seeds)}  max_stage={args.max_stage}  dry_run={args.dry_run} =="
    )

    # Discovery: Exa company search per seed.
    raw: list[dict[str, Any]] = []
    seen_domains: set[str] = set()
    for seed in seeds:
        if cfg.dry_run:
            log(f"  [dry] {seed}")
            continue
        try:
            items = discover_exa.search(
                api_key=cfg.exa_key or "",
                query=seed,
                num_results=args.per_query,
            )
        except Exception as e:  # noqa: BLE001
            log(f"  exa error on {seed[:60]}: {e}")
            continue
        kept = 0
        for it in items:
            domain = it.get("domain") or host_of(it.get("url") or "")
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            it["seed_used"] = seed
            it["bucket"] = "HB"
            it["discovered_at"] = now_iso()
            it["source"] = "exa-company"
            it["company"] = it.get("title") or domain
            raw.append(it)
            kept += 1
        log(f"  + [{kept}/{len(items)}]  {seed[:70]}")

    log(f"\ndiscovery: {len(raw)} unique domains")

    # Enrich: Hunter (HailBytes title priority) → verify → Claude.
    enriched: list[dict[str, Any]] = []
    dropped = {"no_decision_maker": 0, "bad_email": 0, "manual_review": 0, "personalization": 0}
    for cand in raw:
        if len(enriched) >= args.max_stage:
            break
        domain = cand["domain"]
        if cfg.dry_run:
            cand.update(
                {
                    "editor_first_name": "Demo",
                    "editor_last_name": "Lead",
                    "editor_email": f"demo@{domain}",
                    "editor_title": "CTO",
                    "hunter_confidence": 90,
                    "email_status": "valid",
                    "personalized_opener": f"[dry-run opener for {domain} — product {product}]",
                    "lead_score": 70,
                }
            )
            enriched.append(cand)
            continue
        contact = _hunter_with_hb_priority(domain, api_key=cfg.hunter_key or "")
        if not contact:
            dropped["no_decision_maker"] += 1
            continue
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

        cand.update(contact)
        opener, err = _personalize_hailbytes(
            candidate=cand,
            product=product,
            api_key=cfg.anthropic_key or "",
            model=args.model,
        )
        if not opener:
            log(f"  personalization rejected ({err}) for {domain}")
            dropped["personalization"] += 1
            continue
        cand["personalized_opener"] = opener
        cand["email_status"] = "valid"
        cand["lead_score"] = 70  # nominal — qualify gate doesn't apply here
        cand["notes"] = f"hb-{product}"
        enriched.append(cand)
        log(f"  enriched: {cand['editor_email']}  ({domain}, {product})")

    appended = stage_to_sheet(cfg, enriched, dry_run=args.dry_run, tab=SHEET_TAB_HAILBYTES)
    log(
        f"\ndone. raw={len(raw)} enriched={len(enriched)} appended={appended} "
        f"dropped={json.dumps(dropped)}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
