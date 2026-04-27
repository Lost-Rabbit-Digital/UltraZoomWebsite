"""Email verification (NeverBounce by default, ZeroBounce fallback).

Returns one of: ``valid``, ``invalid``, ``risky``, ``unknown``. Only
``valid`` is allowed past this stage; everything else is dropped to the
appropriate review log so a human can promote it later if appropriate.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .cache import JsonCache
from .config import VERIFY_CACHE, VERIFY_TTL_DAYS
from .util import log

NEVERBOUNCE_BASE = "https://api.neverbounce.com/v4"
ZEROBOUNCE_BASE = "https://api.zerobounce.net/v2"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4


def _http_get(url: str) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  verify retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  verify retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("verify: exhausted attempts")


def _via_neverbounce(email: str, api_key: str) -> str:
    params = {"key": api_key, "email": email}
    json_resp = _http_get(f"{NEVERBOUNCE_BASE}/single/check?{urllib.parse.urlencode(params)}")
    result = json_resp.get("result")
    # NeverBounce returns: valid, invalid, disposable, catchall, unknown.
    if result == "valid":
        return "valid"
    if result == "invalid":
        return "invalid"
    if result in {"disposable", "catchall", "unknown"}:
        return "risky"
    return "unknown"


def _via_zerobounce(email: str, api_key: str) -> str:
    params = {"api_key": api_key, "email": email, "ip_address": ""}
    json_resp = _http_get(f"{ZEROBOUNCE_BASE}/validate?{urllib.parse.urlencode(params)}")
    status = (json_resp.get("status") or "").lower()
    if status == "valid":
        return "valid"
    if status == "invalid":
        return "invalid"
    if status in {"catch-all", "spamtrap", "abuse", "do_not_mail"}:
        return "risky"
    return "unknown"


def verify(
    email: str,
    *,
    neverbounce_key: str | None = None,
    zerobounce_key: str | None = None,
    cache: JsonCache | None = None,
) -> str:
    """Return one of: valid, invalid, risky, unknown."""
    if not email:
        return "invalid"
    cache = cache or JsonCache(VERIFY_CACHE, ttl_days=VERIFY_TTL_DAYS)
    cached = cache.get(email)
    if cached is not None:
        return cached

    if neverbounce_key:
        verdict = _via_neverbounce(email, neverbounce_key)
    elif zerobounce_key:
        verdict = _via_zerobounce(email, zerobounce_key)
    else:
        raise RuntimeError("no verifier key configured (NEVERBOUNCE_API_KEY or ZEROBOUNCE_API_KEY)")
    cache.set(email, verdict)
    return verdict
