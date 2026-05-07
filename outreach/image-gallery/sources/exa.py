"""Exa.ai source for niche image queries.

Exa returns URLs to articles that contain images; we fetch each article
and pull its og:image. This is the lowest-quality of the three sources
in v1 — it exists so you can plug in seasonal or topical themes without
adding a new adapter.
"""
from __future__ import annotations

import os
import re
from typing import Iterable, Optional

import requests
from bs4 import BeautifulSoup

from config import USER_AGENT

from .base import Candidate

EXA_URL = "https://api.exa.ai/search"


def _exa_search(query: str, *, num_results: int, api_key: str) -> list[dict]:
    payload = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": True,
        "type": "neural",
        "contents": {"text": {"maxCharacters": 200}},
    }
    r = requests.post(
        EXA_URL,
        headers={"x-api-key": api_key, "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("results", [])


def _og_image(url: str) -> tuple[Optional[str], Optional[str]]:
    """Return (image_url, page_title) by fetching the page."""
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
        r.raise_for_status()
    except requests.RequestException:
        return None, None
    soup = BeautifulSoup(r.text, "html.parser")
    image = None
    for prop in ("og:image", "twitter:image"):
        tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            image = tag["content"].strip()
            break
    title_tag = soup.find("meta", attrs={"property": "og:title"})
    title = title_tag["content"].strip() if title_tag and title_tag.get("content") else None
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    return image, title


def discover(queries: Iterable[str], *, limit_per_query: int = 5) -> list[Candidate]:
    api_key = os.environ.get("EXA_API_KEY")
    if not api_key:
        print("[exa] EXA_API_KEY not set, skipping Exa source")
        return []
    out: list[Candidate] = []
    for q in queries:
        try:
            results = _exa_search(q, num_results=limit_per_query, api_key=api_key)
        except requests.RequestException as e:
            print(f"[exa] '{q}': {e}")
            continue
        for item in results:
            page_url = item.get("url")
            if not page_url:
                continue
            img, page_title = _og_image(page_url)
            if not img:
                continue
            # Stable id: the Exa result id, falling back to a slug of the URL
            sid = item.get("id") or re.sub(r"[^a-z0-9]+", "-", page_url.lower())[:80]
            out.append(Candidate(
                source="exa",
                source_id=sid,
                image_url=img,
                source_url=page_url,
                title=item.get("title") or page_title,
                author=None,
                score=None,
                published_at=item.get("publishedDate"),
                metadata={"query": q},
            ))
    return out
