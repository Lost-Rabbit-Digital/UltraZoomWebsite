"""Append enriched rows to the output Google Sheet.

Auth uses Application Default Credentials via ``google-auth``. In CI,
``google-github-actions/auth@v2`` exchanges the workflow's OIDC token
for a short-lived service-account credential and points
``GOOGLE_APPLICATION_CREDENTIALS`` at the credential file. Locally, run
``gcloud auth application-default login`` once and ADC will pick up
your user credentials. The same code path also accepts a service-
account JSON key file via ``GOOGLE_APPLICATION_CREDENTIALS``.

Boundary rules:
- Append only. Never overwrite, never delete.
- Pipeline writes only the columns it owns. Columns that MailMeteor adds
  (Merge status, Date sent, Opens, Clicks, etc.) are to the right of our
  schema and we never touch them.
- Final dedupe: before append, drop rows whose ``editor_email`` already
  appears in the sheet.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Iterable

from .config import SHEET_COLUMNS, SHEET_TAB, Config
from .util import log, now_iso

SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"
SCOPE = "https://www.googleapis.com/auth/spreadsheets"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


def _column_letter(i: int) -> str:
    s = ""
    n = i
    while True:
        s = chr(65 + (n % 26)) + s
        n = n // 26 - 1
        if n < 0:
            return s


def _http(method: str, url: str, token: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"authorization": f"Bearer {token}"}
    if body is not None:
        headers["content-type"] = "application/json"
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                txt = resp.read().decode("utf-8")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  sheets retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise RuntimeError(f"sheets {method} {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  sheets retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("sheets: exhausted attempts")


class SheetClient:
    def __init__(self, *, sheet_id: str) -> None:
        self._sheet_id = sheet_id
        self._credentials = None
        self._auth_request = None

    def _auth(self) -> str:
        # Lazy import so dry-run / discover-only paths don't pay the cost.
        import google.auth
        import google.auth.exceptions
        import google.auth.transport.requests

        if self._credentials is None:
            try:
                creds, _ = google.auth.default(scopes=[SCOPE])
            except google.auth.exceptions.DefaultCredentialsError as e:
                raise RuntimeError(
                    "no Google credentials found. In CI, confirm the "
                    "google-github-actions/auth step ran. Locally, run "
                    "`gcloud auth application-default login`."
                ) from e
            self._credentials = creds
            self._auth_request = google.auth.transport.requests.Request()

        if not self._credentials.valid:
            self._credentials.refresh(self._auth_request)
        return self._credentials.token

    def ensure_header(self) -> None:
        last_col = _column_letter(len(SHEET_COLUMNS) - 1)
        range_ = f"{SHEET_TAB}!A1:{last_col}1"
        url = f"{SHEETS_BASE}/{self._sheet_id}/values/{urllib.parse.quote(range_)}"
        resp = _http("GET", url, self._auth())
        first = (resp.get("values") or [[]])[0]
        if len(first) >= len(SHEET_COLUMNS):
            return  # already covered (possibly extended by MailMeteor on the right)
        target = list(first)
        while len(target) < len(SHEET_COLUMNS):
            target.append(SHEET_COLUMNS[len(target)])
        put_url = (
            f"{SHEETS_BASE}/{self._sheet_id}/values/{urllib.parse.quote(range_)}"
            "?valueInputOption=RAW"
        )
        _http("PUT", put_url, self._auth(), {"values": [target]})

    def existing_emails(self) -> set[str]:
        """Read the editor_email column. Used as the final dedupe gate
        before append.
        """
        col = _column_letter(SHEET_COLUMNS.index("editor_email"))
        range_ = f"{SHEET_TAB}!{col}2:{col}"
        url = f"{SHEETS_BASE}/{self._sheet_id}/values/{urllib.parse.quote(range_)}"
        resp = _http("GET", url, self._auth())
        out: set[str] = set()
        for row in resp.get("values") or []:
            if row and row[0]:
                out.add(row[0].strip().lower())
        return out

    def append_rows(self, rows: list[list[str]]) -> int:
        if not rows:
            return 0
        range_ = f"{SHEET_TAB}!A1"
        url = (
            f"{SHEETS_BASE}/{self._sheet_id}/values/{urllib.parse.quote(range_)}:append"
            "?valueInputOption=RAW&insertDataOption=INSERT_ROWS"
        )
        _http("POST", url, self._auth(), {"values": rows})
        return len(rows)


def row_for(candidate: dict[str, Any]) -> list[str]:
    """Project an enriched candidate into the sheet's column order. ``status``
    is always ``ready_to_send`` for staged rows (the audit checklist
    requires that).
    """
    row: list[str] = []
    for col in SHEET_COLUMNS:
        if col == "status":
            row.append("ready_to_send")
        elif col == "enriched_at":
            row.append(now_iso())
        elif col == "lead_score":
            row.append(str(candidate.get("lead_score", "")))
        elif col == "hunter_confidence":
            row.append(str(candidate.get("hunter_confidence", "")))
        elif col == "recent_post_url":
            row.append(candidate.get("url", ""))
        elif col == "recent_post_title":
            row.append(candidate.get("title", ""))
        elif col == "recent_post_description":
            row.append(candidate.get("description", ""))
        else:
            row.append(str(candidate.get(col, "") or ""))
    return row


def stage(
    cfg: Config,
    candidates: Iterable[dict[str, Any]],
    *,
    dry_run: bool = False,
) -> int:
    """Append qualifying enriched candidates. Returns the count actually
    appended after the final dedupe gate.
    """
    candidate_list = list(candidates)
    if not candidate_list:
        return 0

    if dry_run:
        log(f"[dry-run] would append {len(candidate_list)} rows to sheet {cfg.sheet_id}")
        return 0

    client = SheetClient(sheet_id=cfg.sheet_id)
    client.ensure_header()
    existing = client.existing_emails()

    rows: list[list[str]] = []
    skipped = 0
    for c in candidate_list:
        email = (c.get("editor_email") or "").strip().lower()
        if not email or email in existing:
            skipped += 1
            continue
        existing.add(email)
        rows.append(row_for(c))

    appended = client.append_rows(rows)
    log(f"stage: appended {appended} rows, skipped {skipped} (already in sheet)")
    return appended
