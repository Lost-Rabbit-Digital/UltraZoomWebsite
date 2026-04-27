"""RSS feed parser for the curated publication list.

Lowest-cost discovery channel. We pull recent items (≤7 days) from each
feed and keep only those whose title or description matches the relevance
keyword set. Uses only stdlib (xml.etree) so the pipeline doesn't need
``feedparser`` as a hard dependency.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from .util import host_of, log

RELEVANCE_KEYWORDS = re.compile(
    r"\b(extension|extensions|chrome|firefox|browser|designer tools?|"
    r"productivity|accessibility|low vision|zoom|magnif(y|ier|ication)|"
    r"privacy|tools? for designers|resource (list|roundup))\b",
    re.IGNORECASE,
)

DEFAULT_MAX_AGE_DAYS = 7

# Atom namespace shows up in some feeds. RSS 2.0 uses no namespace, so we
# fall back to local-name lookups.
ATOM_NS = "{http://www.w3.org/2005/Atom}"


def _load_feed_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    out: list[str] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def _fetch(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"user-agent": "ultra-zoom-outreach/1.0 (+https://ultrazoom.app)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        log(f"  rss fetch failed: {url} — {e}")
        return None


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.strip()
    try:
        # RFC 822 (RSS 2.0)
        return parsedate_to_datetime(s)
    except (TypeError, ValueError):
        pass
    # ISO 8601 (Atom)
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except ValueError:
            continue
    return None


def _text(el: ET.Element | None) -> str:
    return (el.text or "").strip() if el is not None else ""


def _entries_from_root(root: ET.Element) -> list[dict[str, Any]]:
    """Extract entries from either RSS 2.0 or Atom feeds."""
    out: list[dict[str, Any]] = []
    # RSS 2.0: <rss><channel><item>
    for item in root.iter("item"):
        link = _text(item.find("link"))
        if not link:
            continue
        out.append(
            {
                "url": link,
                "title": _text(item.find("title")),
                "description": _text(item.find("description")),
                "published": _parse_date(_text(item.find("pubDate"))),
            }
        )
    # Atom: <feed><entry>
    for entry in root.iter(f"{ATOM_NS}entry"):
        link_el = entry.find(f"{ATOM_NS}link")
        link = link_el.get("href") if link_el is not None else ""
        if not link:
            continue
        summary = _text(entry.find(f"{ATOM_NS}summary")) or _text(
            entry.find(f"{ATOM_NS}content")
        )
        published = _parse_date(_text(entry.find(f"{ATOM_NS}published"))) or _parse_date(
            _text(entry.find(f"{ATOM_NS}updated"))
        )
        out.append(
            {
                "url": link,
                "title": _text(entry.find(f"{ATOM_NS}title")),
                "description": summary,
                "published": published,
            }
        )
    return out


def discover(
    *,
    feed_list_path: Path,
    max_age_days: int = DEFAULT_MAX_AGE_DAYS,
) -> list[dict[str, Any]]:
    feeds = _load_feed_list(feed_list_path)
    if not feeds:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    out: list[dict[str, Any]] = []
    for feed_url in feeds:
        body = _fetch(feed_url)
        if not body:
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError as e:
            log(f"  rss parse failed: {feed_url} — {e}")
            continue

        for entry in _entries_from_root(root):
            published = entry.get("published")
            if published and published < cutoff:
                continue
            haystack = f"{entry['title']} {entry['description']}"
            if not RELEVANCE_KEYWORDS.search(haystack):
                continue
            url = entry["url"]
            out.append(
                {
                    "url": url,
                    "title": entry["title"],
                    "description": " ".join(entry["description"].split())[:400],
                    "domain": host_of(url),
                    "published_date": (
                        published.date().isoformat() if published else ""
                    ),
                }
            )
    return out
