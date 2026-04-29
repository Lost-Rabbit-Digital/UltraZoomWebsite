"""Apollo people-export CSV ingestion.

The pipeline replaces the old Apollo API path with a manual workflow:
run a saved Apollo People search in the UI, export to CSV, drop the file
in ``outreach/inbox/<campaign>/<YYYY-MM-DD>.csv``. This module reads that
CSV and normalizes it into the internal candidate dict shape the rest of
the pipeline expects.

Apollo's column names are stable but verbose. We map a known subset to
short internal field names; everything else is dropped to keep downstream
prompts focused. Rows without a verified email are skipped at ingest
time — defense in depth on top of the saved-search's email-status filter.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from .util import host_of, log, now_iso

# Apollo CSV column → internal field name. Add to this map only when a
# column actively informs personalization or filtering. Columns we never
# read (phone numbers, scoring fields, intent topics) stay out so we don't
# accidentally pass PII the AI doesn't need into the prompt.
APOLLO_COLUMN_MAP: dict[str, str] = {
    "First Name": "first_name",
    "Last Name": "last_name",
    "Title": "editor_title",
    "Company Name": "company",
    "Email": "editor_email",
    "Person Linkedin Url": "linkedin_url",
    "Website": "_website",  # parsed below into ``domain``
    "City": "city",
    "State": "state",
    "Industry": "industry",
    "Keywords": "keywords",
    "Apollo Contact Id": "apollo_contact_id",
    "# Employees": "company_size",
    "Country": "country",
}

# Apollo's "Email Status" column. Only ``Verified`` rows pass through.
EMAIL_STATUS_COL = "Email Status"
ALLOWED_EMAIL_STATUS = {"verified"}


def _strip_phone_prefix(value: str) -> str:
    """Apollo prefixes phone numbers with a literal apostrophe so Excel
    doesn't interpret them as numbers. We don't store phones, but the
    same trick can show up on other free-text columns — strip it.
    """
    if value and value.startswith("'"):
        return value[1:]
    return value


def _normalize_row(row: dict[str, str]) -> dict[str, Any] | None:
    """Map one CSV row to a candidate dict. Returns ``None`` when the row
    fails the email / status floor.
    """
    status = (row.get(EMAIL_STATUS_COL) or "").strip().lower()
    if status not in ALLOWED_EMAIL_STATUS:
        return None

    email = (row.get("Email") or "").strip().lower()
    if not email or "@" not in email:
        return None

    out: dict[str, Any] = {}
    for csv_col, field in APOLLO_COLUMN_MAP.items():
        raw = row.get(csv_col, "") or ""
        out[field] = _strip_phone_prefix(raw.strip())

    # Parse domain from Website. Apollo's ``Website`` is sometimes a bare
    # host, sometimes a full URL; ``host_of`` handles both.
    website = out.pop("_website", "")
    out["domain"] = host_of(website) if website else ""
    if not out["domain"]:
        # Fall back to the email's right-hand side; keeps the row in play
        # when Apollo couldn't resolve the company website.
        out["domain"] = email.split("@", 1)[1]

    out["editor_email"] = email
    return out


def load_csv(path: Path, *, source: str) -> list[dict[str, Any]]:
    """Read an Apollo CSV and return verified-email candidate dicts.

    ``source`` is stamped on every row (e.g. ``"apollo-csv-realtors"``)
    so downstream stages can attribute leads to a campaign batch.
    """
    if not path.exists():
        raise FileNotFoundError(f"Apollo CSV not found: {path}")

    raw_rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_rows.append(row)

    candidates: list[dict[str, Any]] = []
    skipped_no_email = 0
    skipped_status = 0
    discovered_at = now_iso()
    for row in raw_rows:
        normalized = _normalize_row(row)
        if normalized is None:
            status = (row.get(EMAIL_STATUS_COL) or "").strip().lower()
            if status not in ALLOWED_EMAIL_STATUS:
                skipped_status += 1
            else:
                skipped_no_email += 1
            continue
        normalized["discovered_at"] = discovered_at
        normalized["source"] = source
        candidates.append(normalized)

    log(
        f"ingest: {path.name} → {len(candidates)} candidates "
        f"(skipped {skipped_status} unverified, {skipped_no_email} no-email)"
    )
    return candidates


def latest_csv_in(directory: Path) -> Path | None:
    """Find the newest ``*.csv`` in ``directory`` by mtime. Returns
    ``None`` when the directory is empty or doesn't exist.
    """
    if not directory.exists():
        return None
    csvs = sorted(directory.glob("*.csv"), key=lambda p: p.stat().st_mtime)
    return csvs[-1] if csvs else None


def dedupe_by_email(
    candidates: Iterable[dict[str, Any]],
    *,
    against: set[str],
) -> tuple[list[dict[str, Any]], int]:
    """Drop candidates whose lowercase email already appears in
    ``against``. Mutates ``against`` so subsequent calls in the same
    pipeline run see the just-staged emails too.
    """
    out: list[dict[str, Any]] = []
    skipped = 0
    for c in candidates:
        email = (c.get("editor_email") or "").strip().lower()
        if not email or email in against:
            skipped += 1
            continue
        against.add(email)
        out.append(c)
    return out, skipped
