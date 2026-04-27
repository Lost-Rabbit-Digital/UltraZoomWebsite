"""Import Wiza CSV exports into the MailMeteor source Sheet.

Wiza sometimes delivers prospect-list results by **email** as CSV
attachments rather than over the API (e.g. when a list was started in
the Wiza UI, when API enrichment hits a snag, or when Wiza decides the
result set is large enough to batch-deliver). Those credits are paid
for either way, so this importer rescues the CSVs and lands the rows
in the same per-campaign tab the Wiza-direct workflows write to:

    WIZA_uz_*.csv  → "UltraZoom" tab
    WIZA_hb_*.csv  → "HailBytes" tab
    (override with --tab)

Inputs are local CSV files and/or http(s) URLs (the temporary download
links Wiza puts in the email work fine — paste them on the CLI or in
the workflow_dispatch input). The schema we map to lives in
``outreach.config.SHEET_COLUMNS`` and matches what ``stage_sheet``
writes from the API path, so MailMeteor reads both lanes uniformly.

CLI:

    python -m outreach.import_wiza_csv \\
        ~/Downloads/WIZA_uz_trademark_attorney_*.csv \\
        ~/Downloads/WIZA_hb-asm_*.csv \\
        --personalize

The importer dedupes per-tab against ``editor_email`` (and against
``recent_post_url`` for ``--include-no-email`` rows whose email Wiza
couldn't find) so re-running on the same CSVs is safe.
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from .config import (
    DEFAULT_MODEL,
    SHEET_COLUMNS,
    SHEET_TAB_HAILBYTES,
    SHEET_TAB_UZ_PEOPLE,
    Config,
    ensure_dirs,
)
from .stage_sheet import SheetClient, _column_letter, row_for
from .util import log, now_iso

# Filename → tab heuristics. Filenames look like
#   WIZA_hb-asm-penetration-testing-...csv
#   WIZA_uz-trademark-attorney-...csv
HB_PATTERNS = (re.compile(r"(?i)\bwiza[_-]?hb[_-]"), re.compile(r"(?i)\bhb[_-](asm|sat|mssp)"))
UZ_PATTERNS = (re.compile(r"(?i)\bwiza[_-]?uz[_-]"), re.compile(r"(?i)\buz[_-](people|power)"))

# Wiza CSV column → candidate dict shape. We accept a few historical
# header spellings; lowercased + stripped lookups keep things forgiving.
WIZA_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "email": ("email", "work_email"),
    "email_status": ("email_status", "status"),
    "first_name": ("first_name", "firstname"),
    "last_name": ("last_name", "lastname"),
    "full_name": ("full_name", "name"),
    "title": ("title", "job_title"),
    "linkedin": ("linkedin", "linkedin_profile_url", "profile_url"),
    "domain": ("domain", "company_domain"),
    "company": ("company", "company_name"),
    "company_description": ("company_description", "description"),
    "list_name": ("list_name", "list"),
}


def _http_download(url: str, dest_dir: Path) -> Path:
    """Stream a Wiza CSV download URL to a temp file. Returns the path.
    The dest filename is derived from the URL path so the tab heuristic
    still works on the saved name.
    """
    parsed = urllib.parse.urlparse(url)
    name = Path(urllib.parse.unquote(parsed.path)).name or "wiza_download.csv"
    if not name.lower().endswith(".csv"):
        name = name + ".csv"
    out_path = dest_dir / name
    req = urllib.request.Request(
        url,
        headers={"user-agent": "UltraZoom-Outreach/1.0 (+https://ultrazoom.app)"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp, out_path.open("wb") as f:
        while True:
            chunk = resp.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)
    log(f"  downloaded {url} → {out_path}")
    return out_path


def _resolve_inputs(inputs: list[str], download_dir: Path) -> list[Path]:
    paths: list[Path] = []
    download_dir.mkdir(parents=True, exist_ok=True)
    for item in inputs:
        if item.startswith("http://") or item.startswith("https://"):
            paths.append(_http_download(item, download_dir))
            continue
        p = Path(item).expanduser()
        if p.is_dir():
            paths.extend(sorted(p.glob("*.csv")))
        elif p.is_file():
            paths.append(p)
        else:
            log(f"  ! skipping (not found): {item}")
    return paths


def _tab_for_filename(name: str, *, override: str | None) -> str:
    if override:
        return override
    for pat in HB_PATTERNS:
        if pat.search(name):
            return SHEET_TAB_HAILBYTES
    for pat in UZ_PATTERNS:
        if pat.search(name):
            return SHEET_TAB_UZ_PEOPLE
    # Default: UltraZoom. The product without a specific cue is more
    # forgiving — UZ is the primary lane here.
    return SHEET_TAB_UZ_PEOPLE


def _pick(row: dict[str, str], canonical: str) -> str:
    for alias in WIZA_HEADER_ALIASES.get(canonical, (canonical,)):
        v = row.get(alias)
        if v is None:
            v = row.get(alias.lower())
        if v:
            return v.strip()
    return ""


def _to_candidate(row: dict[str, str], *, csv_name: str, source: str) -> dict[str, Any]:
    full_name = _pick(row, "full_name")
    first = _pick(row, "first_name")
    last = _pick(row, "last_name")
    if not first and full_name:
        parts = full_name.split()
        first = parts[0] if parts else ""
        last = " ".join(parts[1:]) if len(parts) > 1 else last

    email = _pick(row, "email")
    status = (_pick(row, "email_status") or ("valid" if email else "unfound")).lower()
    title = _pick(row, "title")
    linkedin = _pick(row, "linkedin")
    domain = _pick(row, "domain")
    company = _pick(row, "company")
    description = _pick(row, "company_description")
    list_name = _pick(row, "list_name") or csv_name

    return {
        "discovered_at": now_iso(),
        "source": source,
        "seed_used": list_name,
        "domain": domain,
        "url": linkedin,
        "title": title,
        "description": description,
        "published_date": "",
        "lead_score": 60 if email else 30,
        "editor_first_name": first,
        "editor_last_name": last,
        "editor_email": email,
        "editor_title": title,
        "editor_company": company,
        "hunter_confidence": 90 if email and status == "valid" else 0,
        "email_status": status,
        "personalized_opener": "",
        "notes": f"wiza-csv | {csv_name}",
        # Used internally by the importer for the tab-tagged dedupe of
        # no-email rows; the column doesn't exist in the sheet schema.
        "_linkedin": linkedin,
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    """Return a list of row dicts. Auto-detects encoding (utf-8 first,
    fallback to utf-8-sig + latin-1). Wiza's exports include a BOM.
    """
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover — latin-1 always succeeds
        text = raw.decode("utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [{(k or "").strip(): (v or "") for k, v in row.items()} for row in reader]


def _existing_linkedin_urls(client: SheetClient) -> set[str]:
    """Pull the recent_post_url column off the target tab so we can
    dedupe ``--include-no-email`` rows that all share an empty email.
    """
    col = _column_letter(SHEET_COLUMNS.index("recent_post_url"))
    range_ = f"{client._tab}!{col}2:{col}"
    url = (
        "https://sheets.googleapis.com/v4/spreadsheets/"
        f"{client._sheet_id}/values/{urllib.parse.quote(range_)}"
    )
    from .stage_sheet import _http  # local import keeps module load light

    resp = _http("GET", url, client._auth())
    out: set[str] = set()
    for row in resp.get("values") or []:
        if row and row[0]:
            out.add(row[0].strip().lower())
    return out


def _personalize(
    cand: dict[str, Any],
    *,
    tab: str,
    api_key: str,
    model: str,
) -> str:
    """Generate a one-shot opener using the campaign-appropriate prompt.
    Returns "" on failure (we still append the row, just without an
    opener — MailMeteor will flag empty merge fields and you can fill
    them in by hand on the high-value rows).
    """
    if not api_key:
        return ""
    # Local imports so a `--no-personalize` run never pulls Anthropic deps.
    from .enrich_personalize import MODEL_IDS, _call_anthropic

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

    # UltraZoom path — same prompt template as run_uz_people.
    from .run_uz_people import PROMPT_PATH, _validate_opener

    try:
        prompt = PROMPT_PATH.read_text()
    except FileNotFoundError:
        return ""
    rendered = (
        prompt.replace("{first_name}", cand.get("editor_first_name", ""))
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


def _row_for_import(cand: dict[str, Any]) -> list[str]:
    """Lean version of stage_sheet.row_for that uses our pre-set status
    and enriched_at, and keeps Wiza's email_status (e.g. ``unfound``)
    instead of forcing ``valid``.
    """
    out: list[str] = []
    for col in SHEET_COLUMNS:
        if col == "status":
            # ready_to_send only when an email exists; otherwise mark for
            # manual review so MailMeteor's `status = ready_to_send`
            # filter naturally excludes them.
            out.append("ready_to_send" if cand.get("editor_email") else "manual_review")
        elif col == "enriched_at":
            out.append(now_iso())
        elif col == "lead_score":
            out.append(str(cand.get("lead_score", "")))
        elif col == "hunter_confidence":
            out.append(str(cand.get("hunter_confidence", "")))
        elif col == "recent_post_url":
            out.append(cand.get("url", ""))
        elif col == "recent_post_title":
            out.append(cand.get("title", ""))
        elif col == "recent_post_description":
            out.append(cand.get("description", ""))
        else:
            out.append(str(cand.get(col, "") or ""))
    return out


def _import_one(
    *,
    cfg: Config,
    path: Path,
    tab_override: str | None,
    include_no_email: bool,
    personalize: bool,
    model: str,
    limit: int | None,
    dry_run: bool,
) -> dict[str, int]:
    rows = _read_csv(path)
    csv_name = path.name
    tab = _tab_for_filename(csv_name, override=tab_override)
    source = "wiza-csv-uz" if tab == SHEET_TAB_UZ_PEOPLE else "wiza-csv-hb"

    log(f"\n→ {csv_name}  ({len(rows)} rows → tab '{tab}')")

    candidates: list[dict[str, Any]] = []
    skipped_no_email = 0
    for r in rows:
        cand = _to_candidate(r, csv_name=csv_name, source=source)
        if not cand["editor_email"] and not include_no_email:
            skipped_no_email += 1
            continue
        if not cand["editor_email"] and not cand.get("_linkedin"):
            # Truly nothing to dedupe on — skip even with --include-no-email.
            skipped_no_email += 1
            continue
        candidates.append(cand)
        if limit is not None and len(candidates) >= limit:
            break

    log(f"  parsed: {len(candidates)} candidates  skipped_no_email: {skipped_no_email}")

    if dry_run:
        for c in candidates[:3]:
            log(f"  [dry] {c['editor_email'] or '(no-email)'}  {c['_linkedin']}")
        return {
            "parsed": len(candidates),
            "appended": 0,
            "skipped_no_email": skipped_no_email,
            "skipped_dupe": 0,
            "personalized": 0,
        }

    client = SheetClient(sheet_id=cfg.sheet_id, tab=tab)
    client.ensure_header()
    existing_emails = client.existing_emails()
    existing_linkedin: set[str] = set()
    if include_no_email:
        existing_linkedin = _existing_linkedin_urls(client)

    sheet_rows: list[list[str]] = []
    skipped_dupe = 0
    personalized = 0
    for cand in candidates:
        email = (cand.get("editor_email") or "").strip().lower()
        link = (cand.get("_linkedin") or "").strip().lower()
        if email:
            if email in existing_emails:
                skipped_dupe += 1
                continue
            existing_emails.add(email)
        else:
            if link and link in existing_linkedin:
                skipped_dupe += 1
                continue
            if link:
                existing_linkedin.add(link)

        if personalize and email and cfg.anthropic_key:
            opener = _personalize(cand, tab=tab, api_key=cfg.anthropic_key, model=model)
            if opener:
                cand["personalized_opener"] = opener
                personalized += 1

        sheet_rows.append(_row_for_import(cand))

    appended = client.append_rows(sheet_rows)
    log(
        f"  appended={appended}  skipped_dupe={skipped_dupe}  personalized={personalized}"
    )
    return {
        "parsed": len(candidates),
        "appended": appended,
        "skipped_no_email": skipped_no_email,
        "skipped_dupe": skipped_dupe,
        "personalized": personalized,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.import_wiza_csv")
    p.add_argument(
        "inputs",
        nargs="+",
        help="CSV file paths, directories, or http(s) URLs (e.g. the "
        "Wiza email's download links).",
    )
    p.add_argument(
        "--tab",
        choices=[SHEET_TAB_UZ_PEOPLE, SHEET_TAB_HAILBYTES],
        help="Force all CSVs into this tab. Default: auto-detect from "
        "filename (WIZA_uz_* → UltraZoom, WIZA_hb_* → HailBytes).",
    )
    p.add_argument(
        "--include-no-email",
        action="store_true",
        help="Also append rows where Wiza couldn't find an email "
        "(email_status=unfound). Status is set to 'manual_review' so "
        "MailMeteor's ready_to_send filter excludes them. Deduped by "
        "LinkedIn URL.",
    )
    p.add_argument(
        "--personalize",
        action="store_true",
        help="Generate a Claude opener for each appended row that has a "
        "valid email. Requires ANTHROPIC_API_KEY.",
    )
    p.add_argument("--no-personalize", dest="personalize", action="store_false")
    p.set_defaults(personalize=True)
    p.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=["haiku", "sonnet", "opus"],
        help="Anthropic model for the opener. Default: haiku.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Cap the number of rows imported per CSV (smoke-test aid).",
    )
    p.add_argument(
        "--download-dir",
        default=str(Path(os.environ.get("RUNNER_TEMP") or "/tmp") / "wiza-imports"),
        help="Where to save CSVs downloaded from URL inputs.",
    )
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()
    cfg = Config.from_env(dry_run=args.dry_run)

    paths = _resolve_inputs(args.inputs, Path(args.download_dir))
    if not paths:
        log("error: no CSV inputs resolved")
        return 1

    if args.personalize and not cfg.anthropic_key and not args.dry_run:
        log("note: --personalize requested but ANTHROPIC_API_KEY missing; skipping openers")

    totals = {"parsed": 0, "appended": 0, "skipped_no_email": 0, "skipped_dupe": 0, "personalized": 0}
    for path in paths:
        try:
            stats = _import_one(
                cfg=cfg,
                path=path,
                tab_override=args.tab,
                include_no_email=args.include_no_email,
                personalize=args.personalize and bool(cfg.anthropic_key),
                model=args.model,
                limit=args.limit,
                dry_run=args.dry_run,
            )
        except Exception as e:  # noqa: BLE001
            log(f"  ! {path.name} failed: {e}")
            continue
        for k, v in stats.items():
            totals[k] = totals.get(k, 0) + v

    log(
        "\n=== summary ===\n"
        f"  files       {len(paths)}\n"
        f"  parsed      {totals['parsed']}\n"
        f"  appended    {totals['appended']}\n"
        f"  personalized {totals['personalized']}\n"
        f"  skipped (no email) {totals['skipped_no_email']}\n"
        f"  skipped (dupe)     {totals['skipped_dupe']}"
    )
    return 0


def _iter_inputs(seq: Iterable[str]) -> list[str]:  # pragma: no cover — convenience
    return [s for s in seq if s and s.strip()]


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
