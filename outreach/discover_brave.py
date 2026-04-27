"""Brave Web Search client for discovery.

Brave is the broad-coverage primary source. Cache key is
``(seed, YYYY-MM-DD)`` so reruns the same day are free; the next day's
run picks up fresh results.
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from .cache import JsonCache
from .config import BRAVE_CACHE
from .util import host_of, log, to_iso_date

BRAVE_BASE = "https://api.search.brave.com/res/v1/web/search"
MIN_GAP_SECONDS = 1.1  # free tier: 1 rps with 100ms slack
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4

_last_call_at = 0.0


def _throttle() -> None:
    global _last_call_at
    gap = time.time() - _last_call_at
    if gap < MIN_GAP_SECONDS:
        time.sleep(MIN_GAP_SECONDS - gap)
    _last_call_at = time.time()


def _call(api_key: str, query: str, count: int) -> dict[str, Any]:
    params = {
        "q": query,
        "count": str(min(20, count)),
        "safesearch": "moderate",
    }
    url = f"{BRAVE_BASE}?{urllib.parse.urlencode(params)}"
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        _throttle()
        req = urllib.request.Request(
            url,
            headers={
                "accept": "application/json",
                "x-subscription-token": api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8")
                import json as _json

                return _json.loads(body)
        except urllib.error.HTTPError as e:  # noqa: PERF203
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  brave retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  brave retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("brave: exhausted attempts")


def _normalize(item: dict[str, Any]) -> dict[str, Any] | None:
    url = item.get("url")
    if not url:
        return None
    return {
        "url": url,
        "title": (item.get("title") or "").strip(),
        "description": (item.get("description") or "").strip(),
        "domain": host_of(url),
        "published_date": to_iso_date(item.get("page_age") or item.get("age") or ""),
    }


def search(
    *,
    api_key: str,
    seed: str,
    num_results: int = 15,
    cache: JsonCache | None = None,
) -> list[dict[str, Any]]:
    cache = cache or JsonCache(BRAVE_CACHE)
    today = datetime.utcnow().date().isoformat()
    cache_key = f"{today}|{seed}|{num_results}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    json_resp = _call(api_key, seed, num_results)
    raw_items = (json_resp.get("web") or {}).get("results") or []
    normalized = [n for n in (_normalize(r) for r in raw_items) if n]
    cache.set(cache_key, normalized)
    return normalized
