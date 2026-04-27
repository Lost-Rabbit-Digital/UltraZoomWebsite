"""Exa.ai semantic search client.

Two endpoints: ``/search`` for natural-language queries, ``/findSimilar``
for "more like this" against a known good URL. Exa returns lower volume
than Brave but higher quality — especially for finding listicles that
*talk about* a topic without using exact keywords.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from .cache import JsonCache
from .config import EXA_CACHE
from .util import host_of, log, to_iso_date

EXA_BASE = "https://api.exa.ai"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4

EXCLUDE_DOMAINS = [
    "chromewebstore.google.com",
    "chrome.google.com",
    "addons.mozilla.org",
    "microsoftedge.microsoft.com",
    "play.google.com",
    "apps.apple.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "pinterest.com",
    "github.com",
    "stackoverflow.com",
    "google.com",
    "bing.com",
    "ultrazoom.app",
    "blogspot.com",
]


def _call(path: str, body: dict[str, Any], api_key: str) -> dict[str, Any]:
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(
            EXA_BASE + path,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  exa retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  exa retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("exa: exhausted attempts")


def _normalize(r: dict[str, Any]) -> dict[str, Any] | None:
    url = r.get("url")
    if not url:
        return None
    text = r.get("text") or r.get("summary") or ""
    return {
        "url": url,
        "title": (r.get("title") or "").strip(),
        "description": " ".join(text.split()).strip()[:300],
        "domain": host_of(url),
        "published_date": to_iso_date(r.get("publishedDate") or ""),
        "exa_score": r.get("score"),
    }


def search(
    *,
    api_key: str,
    query: str,
    num_results: int = 15,
    cache: JsonCache | None = None,
) -> list[dict[str, Any]]:
    cache = cache or JsonCache(EXA_CACHE)
    today = datetime.utcnow().date().isoformat()
    cache_key = f"search|{today}|{query}|{num_results}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    body = {
        "query": query,
        "numResults": num_results,
        "type": "auto",
        "excludeDomains": EXCLUDE_DOMAINS,
        "contents": {"text": {"maxCharacters": 400}},
    }
    json_resp = _call("/search", body, api_key)
    items = [n for n in (_normalize(r) for r in json_resp.get("results", [])) if n]
    cache.set(cache_key, items)
    return items


def find_similar(
    *,
    api_key: str,
    url: str,
    num_results: int = 15,
    cache: JsonCache | None = None,
) -> list[dict[str, Any]]:
    cache = cache or JsonCache(EXA_CACHE)
    today = datetime.utcnow().date().isoformat()
    cache_key = f"similar|{today}|{url}|{num_results}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    body = {
        "url": url,
        "numResults": num_results,
        "excludeSourceDomain": True,
        "excludeDomains": EXCLUDE_DOMAINS,
        "contents": {"text": {"maxCharacters": 400}},
    }
    json_resp = _call("/findSimilar", body, api_key)
    items = [n for n in (_normalize(r) for r in json_resp.get("results", [])) if n]
    cache.set(cache_key, items)
    return items


# Known-good targets for findSimilar, keyed by seed bucket. Each list is
# pre-vetted listicles or resource directories that Exa's similarity
# graph reliably expands into comparable articles. Buckets without a
# specific entry fall back to ``_default``.
KNOWN_GOOD_TARGETS: dict[str, list[str]] = {
    "_default": [
        "https://www.smartupworld.com/best-firefox-extensions-for-everyone/",
        "https://www.designerdaily.com/web-designer-resources",
        "https://www.makeuseof.com/tag/best-chrome-extensions/",
        "https://www.howtogeek.com/the-best-chrome-extensions/",
    ],
    "E": [
        "https://familytreemagazine.com/free-genealogy-websites/",
        "https://blog.eogn.com/",
        "https://www.familyhistorydaily.com/genealogy-help-and-how-to/",
        "https://www.geneabloggers.com/",
    ],
    "F": [
        "https://www.afb.org/aw/",
        "https://webaim.org/articles/",
        "https://accessibility.com/",
        "https://www.perkins.org/resource/",
    ],
}


def targets_for(bucket: str) -> list[str]:
    return KNOWN_GOOD_TARGETS.get(bucket) or KNOWN_GOOD_TARGETS["_default"]
