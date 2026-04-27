"""Wiza Prospect Search and Prospect List clients.

Two endpoints used:

  POST /api/prospects/search
      Synchronous preview. Free (no credits). Returns up to 30 LinkedIn
      profiles matching the filter object — name, title, company, URL —
      but no email. Used to size a niche before spending credits on it.

  POST /api/prospects/create_prospect_list
      Async. Returns a list_id; processing happens in the background and
      charges credits only for the profiles that were actually enriched.
      We poll GET /api/lists/{id} until status is "finished" / "complete",
      then GET /api/lists/{id}/contacts?segment=valid for the rows.

Auth: ``Authorization: Bearer <WIZA_API_KEY>`` header.

Cache rules (file-backed, see cache.py):
  - filter preview (``preview|<hash>|<YYYY-MM-DD>``): 1 day
  - list contents (``contacts|<list_id>``): persistent
  No cache on list creation itself: each create_prospect_list call really
  does charge credits, and the list_id we return is the receipt.

API references:
  https://docs.wiza.co/api-reference/prospect/prospect-search
  https://docs.wiza.co/api-reference/prospect-lists/create-prospect-list
  https://docs.wiza.co/api-reference/lists/get-list
  https://docs.wiza.co/api-reference/lists/get-list-contacts
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from typing import Any

from .cache import JsonCache
from .config import CACHE_DIR
from .util import log

WIZA_BASE = "https://wiza.co/api"
WIZA_PREVIEW_CACHE = CACHE_DIR / "wiza_preview_cache.json"
WIZA_CONTACTS_CACHE = CACHE_DIR / "wiza_contacts_cache.json"
PREVIEW_TTL_DAYS = 1

RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4

# Reveal lists for ~5–25 profiles typically finish in 30–120s. Cap at
# 6 minutes so a stuck job doesn't hold up the workflow timeout.
POLL_INTERVAL_S = 6
POLL_MAX_ATTEMPTS = 60

FINISHED_STATUSES = {"finished", "complete", "completed"}
FAILED_STATUSES = {"failed", "error"}


def _http(
    method: str,
    path: str,
    *,
    api_key: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = WIZA_BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "authorization": f"Bearer {api_key}",
        "accept": "application/json",
    }
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
                log(f"  wiza retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  wiza retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("wiza: exhausted attempts")


def _hash_filters(filters: dict[str, Any]) -> str:
    """Stable cache key for a filter object — order-independent so two
    semantically equivalent filters share a cache slot.
    """
    canonical = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]


def preview(
    *,
    api_key: str,
    filters: dict[str, Any],
    size: int = 30,
    cache: JsonCache | None = None,
) -> dict[str, Any]:
    """Free prospect-search call. Returns ``{"total": int, "profiles": [...]}``
    where each profile carries name/title/company/linkedin_url. No email.
    """
    cache = cache or JsonCache(WIZA_PREVIEW_CACHE, ttl_days=PREVIEW_TTL_DAYS)
    key = f"preview|{_hash_filters(filters)}|{size}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    body = {"filters": filters, "size": min(30, max(1, size))}
    resp = _http("POST", "/prospects/search", api_key=api_key, body=body)
    data = resp.get("data") or {}
    out = {
        "total": int(data.get("total") or 0),
        "profiles": data.get("profiles") or [],
    }
    cache.set(key, out)
    return out


def create_list(
    *,
    api_key: str,
    name: str,
    filters: dict[str, Any],
    max_profiles: int,
    enrichment_level: str = "partial",
    accept_personal_emails: bool = False,
) -> dict[str, Any]:
    """Submit a prospect list for async enrichment. Returns the API
    response containing ``data.id`` (the list_id) and ``data.status``.

    enrichment_level:
        partial — emails only (default; 2 API email credits per result)
        full    — emails + phones (more expensive)
        none    — no email/phone discovery (free; useful for sanity checks)
    """
    body = {
        "list": {
            "name": name[:120],
            "max_profiles": max_profiles,
            "enrichment_level": enrichment_level,
            "email_options": {
                "accept_work": True,
                "accept_personal": accept_personal_emails,
                "accept_generic": False,
            },
        },
        "filters": filters,
    }
    resp = _http("POST", "/prospects/create_prospect_list", api_key=api_key, body=body)
    return resp


def get_list_status(*, api_key: str, list_id: int | str) -> dict[str, Any]:
    return _http("GET", f"/lists/{list_id}", api_key=api_key)


def wait_for_list(
    *,
    api_key: str,
    list_id: int | str,
    interval_s: int = POLL_INTERVAL_S,
    max_attempts: int = POLL_MAX_ATTEMPTS,
) -> str:
    """Poll the list until it reaches a terminal status. Returns the final
    status string (one of FINISHED_STATUSES / FAILED_STATUSES, or "timeout").
    """
    for attempt in range(max_attempts):
        try:
            resp = get_list_status(api_key=api_key, list_id=list_id)
        except urllib.error.HTTPError as e:
            log(f"  wiza list-status HTTP {e.code} on attempt {attempt + 1}")
            if e.code in {402, 403, 404}:
                return "failed"
            time.sleep(interval_s)
            continue
        data = resp.get("data") or resp
        status = (data.get("status") or "").lower()
        if status in FINISHED_STATUSES:
            return status
        if status in FAILED_STATUSES:
            return status
        time.sleep(interval_s)
    return "timeout"


def get_contacts(
    *,
    api_key: str,
    list_id: int | str,
    segment: str = "valid",
    cache: JsonCache | None = None,
) -> list[dict[str, Any]]:
    """Fetch enriched contacts for a finished list. ``segment`` is one of
    ``valid`` (default — passed Wiza's internal verification),
    ``risky`` (caught a soft signal), or ``people`` (everything).
    """
    cache = cache or JsonCache(WIZA_CONTACTS_CACHE)
    key = f"contacts|{list_id}|{segment}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    resp = _http(
        "GET",
        f"/lists/{list_id}/contacts?segment={segment}",
        api_key=api_key,
    )
    data = resp.get("data") or resp
    contacts = data.get("contacts") if isinstance(data, dict) else None
    if contacts is None and isinstance(data, list):
        contacts = data
    contacts = contacts or []
    cache.set(key, contacts)
    return contacts


def to_candidate(contact: dict[str, Any], *, bucket: str, source: str) -> dict[str, Any]:
    """Project a Wiza contact dict into the shape stage_sheet expects.
    Mirrors fields from enrich_hunter / enrich_wiza so downstream code
    (verify, personalize, sheet append) doesn't need to branch.
    """
    full_name = (contact.get("full_name") or "").strip()
    first = (contact.get("first_name") or "").strip()
    last = (contact.get("last_name") or "").strip()
    if not first and full_name:
        parts = full_name.split()
        first = parts[0] if parts else ""
        last = " ".join(parts[1:]) if len(parts) > 1 else last
    return {
        "linkedin_url": contact.get("linkedin") or "",
        "url": contact.get("linkedin") or "",
        "title": contact.get("title") or "",
        "summary": contact.get("company_description") or "",
        "description": contact.get("company_description") or "",
        "domain": contact.get("domain") or contact.get("company_domain") or "",
        "company": contact.get("company") or "",
        "editor_first_name": first,
        "editor_last_name": last,
        "editor_email": (contact.get("email") or "").strip(),
        "editor_title": contact.get("title") or "",
        "editor_company": contact.get("company") or "",
        # Wiza pre-validates emails; treat segment=valid as 90 confidence
        # so downstream verify gating doesn't downgrade good rows.
        "hunter_confidence": 90,
        "email_status": (contact.get("email_status") or "valid").lower(),
        "bucket": bucket,
        "source": source,
    }
