"""Thin wrapper around the Exa.ai API for sourcing candidate articles.

We use the /search endpoint with neural ranking and a domain allowlist /
denylist that you can tune. Exa returns URLs + summaries; we then pass
each URL to fetcher.fetch() for the real signal extraction.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional

import requests

EXA_URL = "https://api.exa.ai/search"


@dataclass
class ExaResult:
    url: str
    title: Optional[str]
    published_date: Optional[str]
    score: Optional[float]
    snippet: Optional[str]


def search(
    query: str,
    *,
    api_key: Optional[str] = None,
    num_results: int = 25,
    include_domains: Optional[Iterable[str]] = None,
    exclude_domains: Optional[Iterable[str]] = None,
    start_published_date: Optional[str] = None,  # ISO 8601, e.g. "2024-01-01"
    use_autoprompt: bool = True,
    type_: str = "neural",
) -> list[ExaResult]:
    api_key = api_key or os.environ.get("EXA_API_KEY")
    if not api_key:
        raise RuntimeError("EXA_API_KEY not set")

    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "type": type_,
        "contents": {"text": {"maxCharacters": 500}},
    }
    if include_domains:
        payload["includeDomains"] = list(include_domains)
    if exclude_domains:
        payload["excludeDomains"] = list(exclude_domains)
    if start_published_date:
        payload["startPublishedDate"] = start_published_date

    r = requests.post(
        EXA_URL,
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    out = []
    for item in data.get("results", []):
        out.append(ExaResult(
            url=item.get("url"),
            title=item.get("title"),
            published_date=item.get("publishedDate"),
            score=item.get("score"),
            snippet=(item.get("text") or "")[:500],
        ))
    return out


# Curated query templates. Add your own as you find what converts.
QUERIES = [
    "military aircraft prototype spotted blurry photo blog post comments",
    "satellite imagery analysis military base reveals blog",
    "leaked image stealth fighter low resolution analysis",
    "aircraft carrier shipyard satellite photo identification",
    "drone reconnaissance photo enhanced detail blog",
    "Chinese fighter jet first flight low quality photo",
    "Russian submarine satellite imagery shipyard",
]

# Reasonable starting allowlist for the military/aviation niche.
# Ordered roughly by quality of comment threads.
DEFAULT_ALLOWLIST = [
    "theaviationist.com",
    "twz.com",                  # The War Zone
    "thedrive.com",
    "hushkit.net",
    "alert5.com",
    "navalnews.com",
    "defensenews.com",
    "warisboring.com",
    "theaviationgeekclub.com",
    "fighterjetsworld.com",
]
