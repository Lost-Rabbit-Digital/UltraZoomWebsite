"""Wiza LinkedIn-URL → email enrichment.

Endpoint: POST ``https://wiza.co/api/individual_reveals``.
Auth: ``Authorization: Bearer <WIZA_API_KEY>`` header.

Wiza's individual-reveal flow is asynchronous: the create call returns
an ``id`` and ``status`` of ``queued`` or ``scraping``. We poll
``GET /api/individual_reveals/{id}`` until status flips to ``finished``,
then read the email + name + title fields.

Cache key is the LinkedIn URL so reruns within TTL are free; misses are
cached as ``{}`` so we don't re-burn credits on profiles that don't
resolve. Wiza credits cost real money — every call is recorded.

API reference:
  https://wiza.co/api/docs
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from .cache import JsonCache
from .config import CACHE_DIR
from .util import log

WIZA_BASE = "https://wiza.co/api"
WIZA_CACHE = CACHE_DIR / "wiza_cache.json"
WIZA_TTL_DAYS = 90
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4

# Reveal jobs typically finish in 5–20s; cap at 90s so a stuck job
# doesn't hold up the entire pipeline run.
POLL_INTERVAL_S = 3
POLL_MAX_ATTEMPTS = 30


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


def _extract(reveal: dict[str, Any]) -> dict[str, Any] | None:
    """Project a finished Wiza reveal into our common contact shape.
    Returns ``None`` when no usable email was returned.
    """
    email = (reveal.get("email") or "").strip()
    if not email:
        return None
    full_name = (reveal.get("full_name") or "").strip()
    first = (reveal.get("first_name") or "").strip()
    last = (reveal.get("last_name") or "").strip()
    if not first and full_name:
        parts = full_name.split()
        first = parts[0] if parts else ""
        last = " ".join(parts[1:]) if len(parts) > 1 else last
    return {
        "editor_first_name": first,
        "editor_last_name": last,
        "editor_email": email,
        "editor_title": (reveal.get("title") or reveal.get("job_title") or "").strip(),
        "editor_company": (reveal.get("company") or reveal.get("company_name") or "").strip(),
        # Wiza doesn't expose a numeric confidence per email; treat a
        # successful reveal as 90 so downstream verify gates still apply.
        "hunter_confidence": 90,
    }


def lookup(
    linkedin_url: str,
    *,
    api_key: str,
    cache: JsonCache | None = None,
) -> dict[str, Any] | None:
    """Resolve a LinkedIn profile URL to a contact dict, or ``None`` on
    miss. Cached for ``WIZA_TTL_DAYS`` to avoid double-billing credits.
    """
    cache = cache or JsonCache(WIZA_CACHE, ttl_days=WIZA_TTL_DAYS)
    cached = cache.get(linkedin_url)
    if cached is not None:
        return cached or None

    try:
        created = _http(
            "POST",
            "/individual_reveals",
            api_key=api_key,
            body={"individual_reveal": {"profile_url": linkedin_url}},
        )
    except urllib.error.HTTPError as e:
        if e.code in {402, 403, 404}:
            cache.set(linkedin_url, {})
            return None
        raise

    payload = (created.get("data") or created) if isinstance(created, dict) else {}
    reveal_id = payload.get("id") or payload.get("uuid")
    status = (payload.get("status") or "").lower()

    # Some Wiza tiers return the email inline on creation; honor that path.
    if status in {"finished", "complete", "completed"} and payload.get("email"):
        result = _extract(payload)
        cache.set(linkedin_url, result or {})
        return result

    if not reveal_id:
        cache.set(linkedin_url, {})
        return None

    for _ in range(POLL_MAX_ATTEMPTS):
        time.sleep(POLL_INTERVAL_S)
        try:
            poll = _http("GET", f"/individual_reveals/{reveal_id}", api_key=api_key)
        except urllib.error.HTTPError as e:
            if e.code in {402, 403, 404}:
                cache.set(linkedin_url, {})
                return None
            raise
        body = (poll.get("data") or poll) if isinstance(poll, dict) else {}
        status = (body.get("status") or "").lower()
        if status in {"finished", "complete", "completed"}:
            result = _extract(body)
            cache.set(linkedin_url, result or {})
            return result
        if status in {"failed", "error"}:
            cache.set(linkedin_url, {})
            return None

    log(f"  wiza poll timeout for {linkedin_url}")
    return None
