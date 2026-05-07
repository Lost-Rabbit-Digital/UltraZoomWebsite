"""Wikimedia Commons + NASA APOD source.

Wikimedia Commons exposes a Picture of the Day generator and a category-
based search. We use the POTD endpoint as the evergreen seed (curated,
free-license) and let the user pass extra Commons categories per run.

NASA APOD is a single image-of-the-day endpoint. ``NASA_API_KEY`` is
optional — DEMO_KEY works for low traffic.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Iterable

import requests

from config import COMMONS_API_URL, NASA_APOD_URL, USER_AGENT

from .base import Candidate

HEADERS = {"User-Agent": USER_AGENT}


def _commons_potd_for(d: date) -> Candidate | None:
    """Return the Wikimedia Picture of the Day for a given date."""
    title = f"Template:Potd/{d.isoformat()}"
    params = {
        "action": "parse",
        "page": title,
        "prop": "wikitext",
        "format": "json",
    }
    try:
        r = requests.get(COMMONS_API_URL, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[commons] POTD {d}: {e}")
        return None
    wikitext = (((r.json() or {}).get("parse") or {}).get("wikitext") or {}).get("*", "")
    # Wikitext for POTD templates is roughly: {{Potd filename|1=Foo.jpg}}
    # We just want the filename token.
    fname = None
    for line in wikitext.splitlines():
        if "Potd filename" in line and "=" in line:
            fname = line.split("=", 1)[1].strip().rstrip("}").rstrip("|")
            break
    if not fname:
        return None
    return _commons_candidate_from_filename(fname, source_id=f"potd-{d.isoformat()}")


def _commons_candidate_from_filename(fname: str, *, source_id: str) -> Candidate | None:
    params = {
        "action": "query",
        "titles": f"File:{fname}",
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|size",
        "format": "json",
    }
    try:
        r = requests.get(COMMONS_API_URL, params=params, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[commons] info {fname}: {e}")
        return None
    pages = (((r.json() or {}).get("query") or {}).get("pages") or {})
    if not pages:
        return None
    page = next(iter(pages.values()))
    info = (page.get("imageinfo") or [{}])[0]
    url = info.get("url")
    if not url:
        return None
    meta = info.get("extmetadata") or {}
    title = (meta.get("ObjectName") or {}).get("value") or fname
    artist = (meta.get("Artist") or {}).get("value")
    return Candidate(
        source="commons",
        source_id=source_id,
        image_url=url,
        source_url=f"https://commons.wikimedia.org/wiki/File:{fname}",
        title=title,
        author=_strip_html(artist) if artist else None,
        score=None,
        published_at=(meta.get("DateTimeOriginal") or {}).get("value"),
        metadata={"license": (meta.get("LicenseShortName") or {}).get("value")},
    )


def _strip_html(s: str) -> str:
    from html.parser import HTMLParser

    class _Stripper(HTMLParser):
        def __init__(self):
            super().__init__()
            self.parts = []
            self.convert_charrefs = True
        def handle_data(self, data): self.parts.append(data)
    p = _Stripper()
    p.feed(s)
    return "".join(p.parts).strip()


def _nasa_apod(*, lookback_days: int) -> list[Candidate]:
    api_key = os.environ.get("NASA_API_KEY", "DEMO_KEY")
    end = date.today()
    start = end - timedelta(days=lookback_days - 1)
    params = {
        "api_key": api_key,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "thumbs": "true",
    }
    try:
        r = requests.get(NASA_APOD_URL, params=params, headers=HEADERS, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"[nasa] apod: {e}")
        return []
    out = []
    for item in r.json() or []:
        # APOD returns 'image' or 'video'; videos often include a thumbnail.
        if item.get("media_type") == "image":
            url = item.get("hdurl") or item.get("url")
        else:
            url = item.get("thumbnail_url")
        if not url:
            continue
        out.append(Candidate(
            source="nasa",
            source_id=f"apod-{item.get('date')}",
            image_url=url,
            source_url=f"https://apod.nasa.gov/apod/ap{(item.get('date') or '').replace('-', '')[2:]}.html",
            title=item.get("title"),
            author=item.get("copyright") or "NASA",
            score=None,
            published_at=item.get("date"),
            metadata={"explanation": (item.get("explanation") or "")[:500]},
        ))
    return out


def discover(
    *,
    commons_potd_days: int = 7,
    nasa_lookback_days: int = 7,
) -> list[Candidate]:
    out: list[Candidate] = []
    today = date.today()
    for n in range(commons_potd_days):
        d = today - timedelta(days=n)
        c = _commons_potd_for(d)
        if c:
            out.append(c)
    out.extend(_nasa_apod(lookback_days=nasa_lookback_days))
    return out
