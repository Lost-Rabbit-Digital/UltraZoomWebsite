"""Apollo.io People Search client.

Replaces the prior Wiza prospect-search/list flow. Apollo bundles the
filter, search, and email reveal into a single endpoint:

  POST /v1/mixed_people/search
      Returns people matching the filter object. Each result carries
      title, company, LinkedIn URL, and (when Apollo already has it on
      file and the account plan allows) a verified work email. Filter
      ``contact_email_status=["verified"]`` to skip rows we'd have to
      pay extra to reveal — those rows aren't useful for cold outreach.

  POST /v1/people/match  (optional, not used by default)
      Per-person enrichment that consumes credits. Worth wiring in
      later for stragglers; the search endpoint already returns enough
      verified emails for the volume targets here.

Auth: ``x-api-key: <APOLLO_API_KEY>`` header.

Cache rules (file-backed, see cache.py):
  - filter search (``search|<hash>|<page>|<YYYY-MM-DD>``): 1 day. Same
    filter on the same day returns the same people; a day-key avoids
    re-billing reruns while still surfacing fresh contacts on the next
    workflow_dispatch.

API references:
  https://docs.apollo.io/reference/people-search
  https://docs.apollo.io/reference/people-enrichment
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from .cache import JsonCache
from .config import CACHE_DIR
from .util import log

APOLLO_BASE = "https://api.apollo.io/api/v1"
APOLLO_SEARCH_CACHE = CACHE_DIR / "apollo_search_cache.json"
SEARCH_TTL_DAYS = 1

RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


def _http(
    method: str,
    path: str,
    *,
    api_key: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = APOLLO_BASE + path
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "accept": "application/json",
        "cache-control": "no-cache",
        "x-api-key": api_key,
        "user-agent": "UltraZoom-Outreach/2.0 (+https://ultrazoom.app)",
    }
    if body is not None:
        headers["content-type"] = "application/json"

    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                txt = resp.read().decode("utf-8")
                return json.loads(txt) if txt else {}
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  apollo retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            try:
                err_body = e.read().decode("utf-8", errors="replace").strip()
                if err_body:
                    log(f"  apollo HTTP {e.code} {method} {path} body: {err_body[:500]}")
            except Exception:  # noqa: BLE001
                pass
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  apollo retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("apollo: exhausted attempts")


def _hash_filters(filters: dict[str, Any]) -> str:
    canonical = json.dumps(filters, sort_keys=True, default=str)
    return hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:16]


def search(
    *,
    api_key: str,
    filters: dict[str, Any],
    per_page: int = 25,
    page: int = 1,
    cache: JsonCache | None = None,
) -> dict[str, Any]:
    """Run /mixed_people/search. Returns ``{"total": int, "people": [...]}``.
    Each person dict carries the raw Apollo shape — pass through
    ``to_candidate`` for the pipeline shape.
    """
    cache = cache or JsonCache(APOLLO_SEARCH_CACHE, ttl_days=SEARCH_TTL_DAYS)
    today = datetime.utcnow().date().isoformat()
    key = f"search|{_hash_filters(filters)}|{per_page}|{page}|{today}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    body = dict(filters)
    body["per_page"] = max(1, min(100, per_page))
    body["page"] = max(1, page)
    resp = _http("POST", "/mixed_people/search", api_key=api_key, body=body)
    pagination = resp.get("pagination") or {}
    out = {
        "total": int(pagination.get("total_entries") or 0),
        "people": resp.get("people") or [],
    }
    cache.set(key, out)
    return out


def preview(*, api_key: str, filters: dict[str, Any]) -> dict[str, Any]:
    """One-page sanity check used to size a niche before pulling more.
    Returns ``{"total": int, "sample": [...]}`` (first 5 people).
    """
    page = search(api_key=api_key, filters=filters, per_page=10, page=1)
    return {"total": page["total"], "sample": page["people"][:5]}


def collect(
    *,
    api_key: str,
    filters: dict[str, Any],
    max_results: int,
    per_page: int = 25,
) -> list[dict[str, Any]]:
    """Walk pages until ``max_results`` people are collected or the source
    runs out. Apollo paginates at 25/50/100; 25 keeps each page small
    enough to fail fast on a bad filter.
    """
    out: list[dict[str, Any]] = []
    page = 1
    while len(out) < max_results:
        chunk = search(api_key=api_key, filters=filters, per_page=per_page, page=page)
        people = chunk.get("people") or []
        if not people:
            break
        out.extend(people)
        if len(people) < per_page:
            break
        page += 1
        if page > 20:  # hard cap to avoid runaway loops
            break
    return out[:max_results]


def _domain_from(person: dict[str, Any]) -> str:
    org = person.get("organization") or {}
    domain = (org.get("primary_domain") or org.get("website_url") or "").strip()
    if domain.startswith("http://") or domain.startswith("https://"):
        from urllib.parse import urlparse

        host = urlparse(domain).hostname or ""
        return host.lower().removeprefix("www.")
    return domain.lower().removeprefix("www.")


def to_candidate(person: dict[str, Any], *, bucket: str, source: str) -> dict[str, Any]:
    """Project an Apollo person into the shape ``stage_sheet`` expects.
    Mirrors the historic field set so the verifier + personalizer don't
    need to know the upstream provider.
    """
    org = person.get("organization") or {}
    first = (person.get("first_name") or "").strip()
    last = (person.get("last_name") or "").strip()
    full_name = (person.get("name") or f"{first} {last}".strip()).strip()
    if not first and full_name:
        parts = full_name.split()
        first = parts[0] if parts else ""
        last = " ".join(parts[1:]) if len(parts) > 1 else last

    email = (person.get("email") or "").strip()
    email_status = (person.get("email_status") or "").lower() or ("verified" if email else "")
    domain = _domain_from(person)
    title = (person.get("title") or "").strip()
    company = (org.get("name") or "").strip()
    summary = (org.get("short_description") or org.get("seo_description") or "").strip()

    return {
        "linkedin_url": person.get("linkedin_url") or "",
        "url": person.get("linkedin_url") or "",
        "title": title,
        "summary": summary,
        "description": summary,
        "domain": domain,
        "company": company,
        "editor_first_name": first,
        "editor_last_name": last,
        "editor_email": email,
        "editor_title": title,
        "editor_company": company,
        # Apollo's "verified" emails are pre-validated; treat them as
        # high-confidence so the downstream verifier doesn't downgrade
        # known-good rows.
        "hunter_confidence": 90 if email_status == "verified" else 60,
        "email_status": email_status or "unknown",
        "bucket": bucket,
        "source": source,
    }
