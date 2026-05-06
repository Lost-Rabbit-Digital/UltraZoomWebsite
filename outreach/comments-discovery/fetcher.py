"""Fetches an article URL and extracts:
  - article metadata (title, og:image, publish date)
  - header image + caption
  - whether comments appear to be open + which system
  - a relevance signal based on zoomable-content keywords

Pure stdlib + requests + beautifulsoup4. No JS execution, so anything
behind a SPA or lazy-loaded comment system may be missed; we flag those
as 'unknown' rather than guessing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36 UltraZoomResearchBot/1.0"
)

# Keywords that suggest the article likely contains imagery worth zooming on.
# Tuned for military / aerospace / tech beats but easy to expand.
ZOOM_SIGNALS = {
    "satellite": ["satellite imagery", "satellite photo", "satellite image", "maxar", "planet labs", "sentinel-", "google earth"],
    "aerial":    ["aerial photo", "reconnaissance", "spy plane", "u-2", "rq-4", "global hawk", "drone footage"],
    "aircraft":  ["fighter", "stealth", "f-22", "f-35", "su-57", "j-20", "b-21", "b-2 spirit", "prototype aircraft"],
    "naval":     ["aircraft carrier", "submarine", "shipyard", "drydock"],
    "leaked":    ["leaked photo", "leaked image", "first look", "spotted", "sighting", "blurry photo", "low resolution"],
    "tech":      ["close-up", "patent drawing", "schematic", "blueprint", "diagram"],
}

COMMENT_INDICATORS = {
    "disqus":     [r"disqus_thread", r"disqus\.com/embed", r"disqus_shortname"],
    "wordpress":  [r"wp-comments-post\.php", r"id=[\"']commentform", r"id=[\"']comments[\"']"],
    "jetpack":    [r"jetpack-comment", r"highlander-comment"],
    "facebook":   [r"fb-comments", r"connect\.facebook\.net.*comments"],
    "intensedebate": [r"intensedebate"],
    "vuukle":     [r"vuukle"],
}

CLOSED_INDICATORS = [
    r"comments are closed",
    r"comments are now closed",
    r"comment(s)? section is closed",
    r"this post is closed for new comments",
]


@dataclass
class FetchResult:
    url: str
    site_title: Optional[str]
    article_title: Optional[str]
    published_at: Optional[str]
    header_image_url: Optional[str]
    header_image_caption: Optional[str]
    image_count: int
    word_count: int
    excerpt: str
    comments_open: bool
    comment_system: Optional[str]
    comment_count: Optional[int]
    last_comment_at: Optional[str]
    zoom_signal: str
    relevance_score: float
    error: Optional[str] = None


def fetch(url: str, timeout: int = 15) -> FetchResult:
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        return _empty(url, error=str(e))

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    site_title = _meta(soup, "og:site_name") or _hostname(url)
    article_title = _meta(soup, "og:title") or (soup.title.string.strip() if soup.title and soup.title.string else None)
    published_at = _meta(soup, "article:published_time") or _meta(soup, "og:article:published_time")
    header_image_url = _meta(soup, "og:image")

    header_caption = _find_header_caption(soup)
    image_count = len(soup.find_all("img"))

    body_text = _extract_body_text(soup)
    word_count = len(body_text.split())
    excerpt = body_text[:500]

    system, comments_open = _detect_comments(html, soup)
    comment_count = _count_comments(soup)
    last_comment_at = _last_comment_date(soup)

    matched_signals = _match_zoom_signals(article_title or "", body_text, header_caption or "")
    score = _score(matched_signals, image_count, comments_open, word_count)

    return FetchResult(
        url=url,
        site_title=site_title,
        article_title=article_title,
        published_at=published_at,
        header_image_url=header_image_url,
        header_image_caption=header_caption,
        image_count=image_count,
        word_count=word_count,
        excerpt=excerpt,
        comments_open=comments_open,
        comment_system=system,
        comment_count=comment_count,
        last_comment_at=last_comment_at,
        zoom_signal=",".join(matched_signals),
        relevance_score=score,
    )


# ---------- helpers ----------

def _empty(url: str, error: str) -> FetchResult:
    return FetchResult(
        url=url, site_title=None, article_title=None, published_at=None,
        header_image_url=None, header_image_caption=None, image_count=0,
        word_count=0, excerpt="", comments_open=False, comment_system=None,
        comment_count=None, last_comment_at=None, zoom_signal="",
        relevance_score=0.0, error=error,
    )


def _meta(soup: BeautifulSoup, prop: str) -> Optional[str]:
    tag = soup.find("meta", attrs={"property": prop}) or soup.find("meta", attrs={"name": prop})
    if tag and tag.get("content"):
        return tag["content"].strip()
    return None


def _hostname(url: str) -> str:
    return urlparse(url).hostname or url


def _find_header_caption(soup: BeautifulSoup) -> Optional[str]:
    # Try <figure> near top of article body
    for fig in soup.find_all("figure", limit=3):
        cap = fig.find("figcaption")
        if cap and cap.get_text(strip=True):
            return cap.get_text(" ", strip=True)
    # Some sites use a div with class containing "caption"
    cap = soup.find("div", class_=re.compile(r"caption|wp-caption-text", re.I))
    if cap and cap.get_text(strip=True):
        return cap.get_text(" ", strip=True)
    return None


def _extract_body_text(soup: BeautifulSoup) -> str:
    # Prefer <article>, fall back to main content area, then body
    container = (
        soup.find("article")
        or soup.find("main")
        or soup.find("div", class_=re.compile(r"post-content|entry-content|article-body", re.I))
        or soup.body
    )
    if not container:
        return ""
    for s in container.find_all(["script", "style", "nav", "aside", "footer", "header"]):
        s.decompose()
    return container.get_text(" ", strip=True)


def _detect_comments(html: str, soup: BeautifulSoup) -> tuple[Optional[str], bool]:
    lower = html.lower()
    # Closed signals override system detection
    for pat in CLOSED_INDICATORS:
        if re.search(pat, lower):
            return _first_match_system(lower), False
    system = _first_match_system(lower)
    if system is None:
        return None, False
    # If we see a comment form, treat as open
    has_form = bool(
        soup.find("form", id=re.compile(r"commentform", re.I))
        or soup.find("form", action=re.compile(r"wp-comments-post", re.I))
        or soup.find("div", id="disqus_thread")
        or soup.find("div", class_=re.compile(r"fb-comments"))
    )
    return system, has_form


def _first_match_system(lower_html: str) -> Optional[str]:
    for system, patterns in COMMENT_INDICATORS.items():
        for pat in patterns:
            if re.search(pat, lower_html):
                return system
    return None


def _count_comments(soup: BeautifulSoup) -> Optional[int]:
    # Heuristic: WordPress often renders <span class="comments-link"> or h2 with count
    for el in soup.find_all(string=re.compile(r"\b(\d+)\s+comments?\b", re.I)):
        m = re.search(r"\b(\d+)\s+comments?\b", el, re.I)
        if m:
            return int(m.group(1))
    return None


def _last_comment_date(soup: BeautifulSoup) -> Optional[str]:
    times = soup.find_all("time", class_=re.compile(r"comment", re.I))
    if not times:
        return None
    last = times[-1]
    return last.get("datetime") or last.get_text(strip=True)


def _match_zoom_signals(title: str, body: str, caption: str) -> list[str]:
    haystack = f"{title} {caption} {body}".lower()
    matched = []
    for category, terms in ZOOM_SIGNALS.items():
        if any(t in haystack for t in terms):
            matched.append(category)
    return matched


def _score(matched: list[str], image_count: int, comments_open: bool, word_count: int) -> float:
    if not comments_open:
        return 0.0
    score = 0.0
    score += min(len(matched), 4) * 0.15        # up to 0.6 from signal categories
    score += min(image_count, 10) * 0.02        # up to 0.2 from image density
    if word_count >= 400:
        score += 0.1                            # avoid thin posts
    if word_count >= 1200:
        score += 0.1                            # long-form gets a small bump
    return round(min(score, 1.0), 3)


if __name__ == "__main__":
    import json, sys
    res = fetch(sys.argv[1])
    print(json.dumps(asdict(res), indent=2))
