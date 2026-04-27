"""Sync finished Wiza prospect lists into the source Sheet via the API.

Wiza was emailing CSVs instead of returning contacts on the API workflow
runs, so a stack of already-paid-for prospect lists never reached the
Sheet. The list IDs are baked into the CSV filenames Wiza emails
(``WIZA_*_ID4964965.csv`` → list_id 4964965), and ``GET /api/lists/
{id}/contacts?segment=valid`` returns the same enriched rows the API
workflow expects — without spending another credit (charge happened at
enrichment time; fetch is free).

Inputs (any combination):
  - List IDs as positional args: 4964965 4964953 4964954
  - --from-filenames <path...>: extract IDs from WIZA_*_ID{N}.csv names
  - --auto: enumerate every list on the account via GET /lists

Tab routing:
  list name starts with "UZ "  → UltraZoom tab
  list name starts with "HB-"  → HailBytes tab
  --tab override forces a specific tab.

Personalization is on by default (set ANTHROPIC_API_KEY); use
--no-personalize to skip Claude and bulk-stage rows for a manual sweep.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from . import discover_wiza
from .config import (
    DEFAULT_MODEL,
    SHEET_TAB_HAILBYTES,
    SHEET_TAB_UZ_PEOPLE,
    Config,
    ensure_dirs,
)
from .stage_sheet import stage as stage_to_sheet
from .util import log, now_iso

# WIZA_*_ID{number}.csv — Wiza embeds the list_id at the tail of every
# emailed export filename.
LIST_ID_FROM_FILENAME = re.compile(r"_ID(\d+)\.csv$", re.IGNORECASE)


def _extract_id(name: str) -> str | None:
    m = LIST_ID_FROM_FILENAME.search(name)
    return m.group(1) if m else None


def _ids_from_filenames(paths: list[str]) -> list[str]:
    out: list[str] = []
    for p in paths:
        path = Path(p).expanduser()
        if path.is_dir():
            files = list(path.glob("*.csv"))
        else:
            files = [path]
        for f in files:
            lid = _extract_id(f.name)
            if lid:
                out.append(lid)
            else:
                log(f"  ! no list_id in filename: {f.name}")
    return out


def _tab_for_list_name(name: str, *, override: str | None) -> str:
    if override:
        return override
    head = (name or "").strip().lower()
    if head.startswith("uz "):
        return SHEET_TAB_UZ_PEOPLE
    if head.startswith("hb-") or head.startswith("hb "):
        return SHEET_TAB_HAILBYTES
    # Fallback heuristic on substrings.
    if "uz-people" in head or " uz " in head:
        return SHEET_TAB_UZ_PEOPLE
    if "hb-asm" in head or "hb-sat" in head or "hailbytes" in head:
        return SHEET_TAB_HAILBYTES
    # Default to UltraZoom — primary lane here.
    return SHEET_TAB_UZ_PEOPLE


def _personalize_for_tab(
    cand: dict[str, Any],
    *,
    tab: str,
    api_key: str,
    model: str,
) -> str:
    if tab == SHEET_TAB_HAILBYTES:
        from .run_hailbytes import _personalize_hailbytes, _pick_product

        product = _pick_product("rotate")
        try:
            opener, _err = _personalize_hailbytes(
                candidate=cand, product=product, api_key=api_key, model=model
            )
            return opener
        except Exception as e:  # noqa: BLE001
            log(f"  personalize error ({cand.get('editor_email')}): {e}")
            return ""

    from .enrich_personalize import MODEL_IDS, _call_anthropic
    from .run_uz_people import PROMPT_PATH, _validate_opener

    try:
        prompt_template = PROMPT_PATH.read_text()
    except FileNotFoundError:
        return ""
    rendered = (
        prompt_template.replace("{first_name}", cand.get("editor_first_name", ""))
        .replace("{title}", cand.get("editor_title", "") or cand.get("title", ""))
        .replace("{niche}", cand.get("seed_used", ""))
        .replace("{summary}", cand.get("description", ""))
    )
    try:
        raw = _call_anthropic(
            api_key, MODEL_IDS.get(model, MODEL_IDS["haiku"]), rendered, max_tokens=300
        )
    except Exception as e:  # noqa: BLE001
        log(f"  personalize error ({cand.get('editor_email')}): {e}")
        return ""
    text = raw.strip().strip('"').strip("'")
    ok, _reason = _validate_opener(text)
    return text if ok else ""


def _sync_one(
    *,
    cfg: Config,
    list_id: str,
    tab_override: str | None,
    segment: str,
    personalize: bool,
    model: str,
    dry_run: bool,
) -> dict[str, int]:
    log(f"\n→ list {list_id}")

    # Pull list metadata to drive tab routing and report status.
    try:
        meta = discover_wiza.get_list_status(api_key=cfg.wiza_key or "", list_id=list_id)
    except Exception as e:  # noqa: BLE001
        log(f"  ! status fetch failed: {e}")
        return {"valid": 0, "appended": 0, "personalized": 0}
    md = meta.get("data") or meta or {}
    list_name = (md.get("name") or "").strip()
    status = (md.get("status") or "").lower()
    log(f"  name='{list_name}'  status={status}")
    if status and status not in discover_wiza.FINISHED_STATUSES:
        log(f"  ! list not finished (status={status}); skipping")
        return {"valid": 0, "appended": 0, "personalized": 0}

    tab = _tab_for_list_name(list_name, override=tab_override)
    source = "wiza-list-uz" if tab == SHEET_TAB_UZ_PEOPLE else "wiza-list-hb"

    try:
        contacts = discover_wiza.get_contacts(
            api_key=cfg.wiza_key or "",
            list_id=list_id,
            segment=segment,
        )
    except Exception as e:  # noqa: BLE001
        log(f"  ! contacts fetch failed: {e}")
        return {"valid": 0, "appended": 0, "personalized": 0}

    log(f"  segment={segment}: {len(contacts)} contacts → tab '{tab}'")

    candidates: list[dict[str, Any]] = []
    for c in contacts:
        cand = discover_wiza.to_candidate(
            c,
            bucket="UZ" if tab == SHEET_TAB_UZ_PEOPLE else "HB",
            source=source,
        )
        if not cand.get("editor_email"):
            continue
        cand["seed_used"] = list_name
        cand["discovered_at"] = now_iso()
        cand["lead_score"] = 60 if tab == SHEET_TAB_UZ_PEOPLE else 70
        cand["notes"] = f"wiza-list:{list_id}"
        candidates.append(cand)

    log(f"  candidates with email: {len(candidates)}")
    if not candidates:
        return {"valid": len(contacts), "appended": 0, "personalized": 0}

    personalized = 0
    if personalize and cfg.anthropic_key and not dry_run:
        for cand in candidates:
            opener = _personalize_for_tab(
                cand, tab=tab, api_key=cfg.anthropic_key, model=model
            )
            if opener:
                cand["personalized_opener"] = opener
                personalized += 1

    appended = stage_to_sheet(cfg, candidates, dry_run=dry_run, tab=tab)
    return {"valid": len(contacts), "appended": appended, "personalized": personalized}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.sync_wiza_lists")
    p.add_argument(
        "list_ids",
        nargs="*",
        help="Wiza list IDs (the trailing number in WIZA_*_ID{N}.csv). "
        "Combine with --from-filenames or --auto.",
    )
    p.add_argument(
        "--from-filenames",
        nargs="+",
        default=[],
        help="Extract list IDs from CSV filenames or directories.",
    )
    p.add_argument(
        "--auto",
        action="store_true",
        help="Enumerate every list on the Wiza account via GET /lists. "
        "Falls back to no-op if the endpoint isn't available.",
    )
    p.add_argument(
        "--tab",
        choices=[SHEET_TAB_UZ_PEOPLE, SHEET_TAB_HAILBYTES],
        help="Force destination tab. Default: route by list name.",
    )
    p.add_argument(
        "--segment",
        choices=["valid", "risky", "people"],
        default="valid",
        help="Wiza segment to fetch. Default: valid (Wiza-pre-verified emails).",
    )
    p.add_argument(
        "--personalize",
        action="store_true",
    )
    p.add_argument("--no-personalize", dest="personalize", action="store_false")
    p.set_defaults(personalize=True)
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])
    p.add_argument(
        "--max-lists",
        type=int,
        default=None,
        help="Cap the number of lists processed this invocation.",
    )
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()
    cfg = Config.from_env(dry_run=args.dry_run)

    if not cfg.wiza_key and not args.dry_run:
        log("error: WIZA_API_KEY missing")
        return 1

    ids: list[str] = list(args.list_ids)
    if args.from_filenames:
        ids.extend(_ids_from_filenames(args.from_filenames))
    if args.auto and not args.dry_run:
        log("→ enumerating lists via GET /lists")
        records = discover_wiza.list_lists(api_key=cfg.wiza_key or "")
        for rec in records:
            lid = rec.get("id") or rec.get("uuid")
            status = (rec.get("status") or "").lower()
            if not lid:
                continue
            if status and status not in discover_wiza.FINISHED_STATUSES:
                continue
            ids.append(str(lid))

    # Stable, deduped order.
    seen: set[str] = set()
    uniq: list[str] = []
    for lid in ids:
        s = str(lid).strip()
        if s and s not in seen:
            seen.add(s)
            uniq.append(s)
    if args.max_lists is not None:
        uniq = uniq[: args.max_lists]

    if not uniq:
        log("error: no list IDs (pass list IDs as args, --from-filenames, or --auto)")
        return 1

    log(f"== sync {len(uniq)} list(s)  segment={args.segment}  dry_run={args.dry_run} ==")

    totals = {"valid": 0, "appended": 0, "personalized": 0}
    for lid in uniq:
        try:
            stats = _sync_one(
                cfg=cfg,
                list_id=lid,
                tab_override=args.tab,
                segment=args.segment,
                personalize=args.personalize and bool(cfg.anthropic_key),
                model=args.model,
                dry_run=args.dry_run,
            )
        except Exception as e:  # noqa: BLE001
            log(f"  ! list {lid} failed: {e}")
            continue
        for k, v in stats.items():
            totals[k] = totals.get(k, 0) + v

    log(
        "\n=== summary ===\n"
        f"  lists        {len(uniq)}\n"
        f"  fetched      {totals['valid']}\n"
        f"  appended     {totals['appended']}\n"
        f"  personalized {totals['personalized']}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
