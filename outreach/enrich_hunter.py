"""Hunter.io editor lookup.

Domain Search ranks contacts by role; we promote ``editor``-flavoured
roles first, then editorial/partnerships, then a short fallback list.
Cache key is the domain so repeat lookups across runs are free until the
cached entry's TTL expires.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .cache import JsonCache
from .config import HUNTER_CACHE, HUNTER_TTL_DAYS
from .util import log

HUNTER_BASE = "https://api.hunter.io/v2"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4

# Highest first. Each tier matches against Hunter's ``position`` and
# ``department`` fields. Anything not on the list is a fallback option
# considered only when no tier matches.
ROLE_TIERS: list[tuple[str, list[str]]] = [
    ("editor", ["editor", "editor-in-chief", "managing editor"]),
    ("content", ["content", "writer", "journalist", "contributor"]),
    ("editorial", ["editorial"]),
    ("partnerships", ["partnerships", "business development", "bd", "biz dev"]),
    ("marketing", ["marketing", "growth"]),
    ("founder", ["founder", "co-founder", "ceo", "owner", "publisher"]),
]


def _call(path: str, params: dict[str, str]) -> dict[str, Any]:
    url = f"{HUNTER_BASE}{path}?{urllib.parse.urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  hunter retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  hunter retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("hunter: exhausted attempts")


def _tier_for(person: dict[str, Any]) -> int:
    """Lower index = higher priority. Returns ``len(ROLE_TIERS)`` when no
    tier matches (fallback bucket).
    """
    haystack = " ".join(
        [
            (person.get("position") or "").lower(),
            (person.get("department") or "").lower(),
            (person.get("seniority") or "").lower(),
        ]
    )
    for idx, (_, keywords) in enumerate(ROLE_TIERS):
        if any(k in haystack for k in keywords):
            return idx
    return len(ROLE_TIERS)


def _confidence(person: dict[str, Any]) -> int:
    """Hunter exposes per-email confidence under either ``confidence`` or
    ``email.confidence`` depending on endpoint. Domain Search returns
    ``confidence`` per email-row.
    """
    val = person.get("confidence") or 0
    try:
        return int(val)
    except (TypeError, ValueError):
        return 0


def _pick_email(emails: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Pick the best email from Hunter's list by (tier, -confidence).
    Returns ``None`` only when the list is empty.
    """
    if not emails:
        return None
    ranked = sorted(emails, key=lambda p: (_tier_for(p), -_confidence(p)))
    return ranked[0]


def lookup(
    domain: str,
    *,
    api_key: str,
    cache: JsonCache | None = None,
) -> dict[str, Any] | None:
    """Return ``{first_name, last_name, email, confidence}`` or ``None``."""
    cache = cache or JsonCache(HUNTER_CACHE, ttl_days=HUNTER_TTL_DAYS)
    cached = cache.get(domain)
    if cached is not None:
        return cached or None  # cached "miss" stored as ``{}``

    try:
        json_resp = _call(
            "/domain-search",
            {"domain": domain, "api_key": api_key, "limit": "10"},
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            cache.set(domain, {})
            return None
        raise

    emails = ((json_resp.get("data") or {}).get("emails")) or []
    pick = _pick_email(emails)
    if not pick or not pick.get("value"):
        cache.set(domain, {})
        return None

    result = {
        "editor_first_name": pick.get("first_name") or "",
        "editor_last_name": pick.get("last_name") or "",
        "editor_email": pick.get("value"),
        "hunter_confidence": _confidence(pick),
    }
    cache.set(domain, result)
    return result
