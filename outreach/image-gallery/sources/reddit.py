"""Reddit top-of-day source.

Uses Reddit's public JSON listings (no OAuth) so we avoid client-credential
plumbing for what is read-only public data. Set a real User-Agent — Reddit
rate-limits anonymous traffic aggressively if you don't.

Filters:
  * post must have a direct image URL (i.imgur, i.redd.it, .jpg/.png/.webp)
  * post must have score >= ``min_score``
  * NSFW posts are skipped (Imgur galleries we target are SFW)
  * crossposts and stickied posts are skipped
"""
from __future__ import annotations

import time
from typing import Iterable
from urllib.parse import urlparse

import requests

from config import REDDIT_MIN_SCORE, REDDIT_TOP_WINDOW, USER_AGENT

from .base import Candidate

LISTING_URL = "https://www.reddit.com/r/{subreddit}/top.json"

DIRECT_IMAGE_HOSTS = {"i.redd.it", "i.imgur.com"}
DIRECT_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _is_direct_image(url: str) -> bool:
    if not url:
        return False
    host = urlparse(url).netloc.lower()
    if host in DIRECT_IMAGE_HOSTS:
        return True
    return url.lower().split("?")[0].endswith(DIRECT_IMAGE_EXTS)


def _normalize_url(post: dict) -> str | None:
    """Pull a direct image URL out of a Reddit post payload.

    Falls back through preview > url_overridden > url. Reddit encodes &
    as &amp; in preview URLs so we unescape.
    """
    url = post.get("url_overridden_by_dest") or post.get("url")
    if _is_direct_image(url):
        return url
    preview = post.get("preview") or {}
    images = preview.get("images") or []
    if images:
        src = images[0].get("source", {}).get("url")
        if src:
            return src.replace("&amp;", "&")
    return None


def discover(
    subreddits: Iterable[str],
    *,
    min_score: int = REDDIT_MIN_SCORE,
    window: str = REDDIT_TOP_WINDOW,
    limit_per_sub: int = 25,
    sleep_between: float = 1.5,
) -> list[Candidate]:
    out: list[Candidate] = []
    for sub in subreddits:
        params = {"t": window, "limit": limit_per_sub}
        try:
            r = requests.get(
                LISTING_URL.format(subreddit=sub),
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[reddit] r/{sub}: {e}")
            time.sleep(sleep_between)
            continue

        data = r.json().get("data", {}).get("children", [])
        for child in data:
            post = child.get("data", {})
            if post.get("over_18") or post.get("stickied") or post.get("is_self"):
                continue
            score = int(post.get("score") or 0)
            if score < min_score:
                continue
            url = _normalize_url(post)
            if not url:
                continue
            out.append(Candidate(
                source="reddit",
                source_id=post["id"],
                image_url=url,
                source_url="https://www.reddit.com" + post.get("permalink", ""),
                title=post.get("title"),
                author=post.get("author"),
                score=score,
                published_at=_unix_to_iso(post.get("created_utc")),
                metadata={
                    "subreddit": sub,
                    "num_comments": post.get("num_comments"),
                    "domain": post.get("domain"),
                },
            ))
        time.sleep(sleep_between)
    return out


def _unix_to_iso(ts) -> str | None:
    if not ts:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
