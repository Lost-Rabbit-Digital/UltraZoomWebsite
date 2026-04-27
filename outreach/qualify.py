"""Filtering, scoring, and dedupe.

Hard filters drop candidates outright. Soft scoring assigns a 0-100
``lead_score``; only candidates with ``score >= MIN_LEAD_SCORE`` advance
to enrichment. Every candidate that survives the hard filters — pass or
fail on score — is recorded in ``seen_urls`` and ``seen_domains`` so we
don't re-process it on a future run.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .config import EXCLUDED_DOMAINS_PATH, MAX_AGE_MONTHS, MIN_LEAD_SCORE
from .discover_exa import KNOWN_GOOD_TARGETS
from .util import host_of, log, today_iso

LISTICLE_TERMS = re.compile(
    r"\b(best|top|essential|must[- ]have|ultimate|favorite|favourite)\b", re.IGNORECASE
)
NUMBERED_LIST = re.compile(r"\b\d{1,3}\s+(tools?|extensions?|apps?|resources?)\b", re.IGNORECASE)
ROUNDUP_TERMS = re.compile(
    r"\b(roundup|directory|resources?|toolbox|toolkit|collection)\b", re.IGNORECASE
)
YEAR_TERMS = re.compile(r"\b(20\d{2}|updated|refresh(ed)?)\b", re.IGNORECASE)
EXTENSION_TERMS = re.compile(r"\b(extensions?|add[- ]?ons?)\b", re.IGNORECASE)
BROWSER_TERMS = re.compile(r"\b(chrome|firefox|edge|safari|brave|opera)\b", re.IGNORECASE)
DESIGNER_TERMS = re.compile(
    r"\b(designer tools?|design resources?|web design|ux design|graphic design)\b",
    re.IGNORECASE,
)
ACCESSIBILITY_TERMS = re.compile(
    r"\b(accessib(le|ility)|low[- ]vision|screen[- ]reader|a11y)\b", re.IGNORECASE
)
PRODUCTIVITY_TERMS = re.compile(r"\b(productivity|workflow)\b", re.IGNORECASE)
PRIVACY_TERMS = re.compile(r"\b(privacy|zero[- ]telemetry|tracker[- ]free)\b", re.IGNORECASE)
SPAM_TERMS = re.compile(r"\b(sponsored|paid (?:post|content)|promotion|advertorial)\b", re.IGNORECASE)

# Soft watchlist of borderline link-farm domains. Rather than hard-block
# (some occasionally publish good content), we just dock score so they
# only stage when the post is otherwise compelling.
SOFT_WATCH_DOMAINS = {
    "medium.com",
    "dev.to",
    "hashnode.dev",
    "substack.com",
}

ENGLISH_HINT = re.compile(r"[A-Za-z]")


def _load_excluded_domains(path: Path = EXCLUDED_DOMAINS_PATH) -> set[str]:
    if not path.exists():
        return set()
    out: set[str] = set()
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.add(s.lower().removeprefix("www."))
    return out


def _is_recent_enough(published: str | None, max_months: int) -> bool:
    """No date is permitted (many publications strip dates from old
    listicles). When a date is present, it must be within ``max_months``.
    """
    if not published:
        return True
    try:
        d = datetime.strptime(published[:10], "%Y-%m-%d")
    except ValueError:
        return True
    cutoff = datetime.utcnow() - timedelta(days=max_months * 31)
    return d >= cutoff


def _looks_english(*texts: str) -> bool:
    """Cheap language gate. Brave already filters by locale; this is a
    last-line defense against feeds in other scripts.
    """
    blob = " ".join(t for t in texts if t)
    if not blob:
        return False
    letters = sum(1 for c in blob if c.isalpha())
    if letters < 10:
        return False
    ascii_letters = sum(1 for c in blob if c.isascii() and c.isalpha())
    return ascii_letters / max(letters, 1) > 0.7


def _is_reachable(url: str, timeout: int = 8) -> bool:
    """HEAD probe with a tight timeout. Fall back to GET when the server
    rejects HEAD (some CDNs do). We treat any 2xx/3xx as reachable; the
    contact-finding step doesn't care which.
    """
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(
                url,
                method=method,
                headers={"user-agent": "ultra-zoom-outreach/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return 200 <= resp.status < 400
        except urllib.error.HTTPError as e:
            if 200 <= e.code < 400:
                return True
            if e.code == 405 and method == "HEAD":
                continue
            return False
        except (urllib.error.URLError, TimeoutError, ValueError, ConnectionError):
            return False
    return False


def score(candidate: dict[str, Any]) -> int:
    title = candidate.get("title", "") or ""
    desc = candidate.get("description", "") or ""
    blob = f"{title} {desc}"
    domain = candidate.get("domain", "") or ""
    source = candidate.get("source", "")
    seed = candidate.get("seed_used", "") or ""

    s = 30

    if LISTICLE_TERMS.search(title) or NUMBERED_LIST.search(title):
        s += 20
    if YEAR_TERMS.search(title):
        s += 10
    if ROUNDUP_TERMS.search(blob):
        s += 15

    if EXTENSION_TERMS.search(blob) and BROWSER_TERMS.search(blob):
        s += 15
    if DESIGNER_TERMS.search(blob):
        s += 10
    if ACCESSIBILITY_TERMS.search(blob):
        s += 10
    if PRODUCTIVITY_TERMS.search(blob):
        s += 5
    if PRIVACY_TERMS.search(blob):
        s += 10

    if source == "rss":
        s += 10
    if source == "exa-similar" and seed in KNOWN_GOOD_TARGETS:
        s += 15

    if SPAM_TERMS.search(blob):
        s -= 20
    if domain in SOFT_WATCH_DOMAINS:
        s -= 15

    return max(0, min(100, s))


def qualify(
    candidates: list[dict[str, Any]],
    *,
    seen_urls: set[str],
    seen_domains: set[str],
    excluded_domains: set[str] | None = None,
    min_score: int = MIN_LEAD_SCORE,
    max_age_months: int = MAX_AGE_MONTHS,
    reachability_check: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply hard filters + scoring.

    Returns ``(qualified, stats)``. ``qualified`` is everything that
    survived the hard filters AND scored ``>= min_score``. ``stats``
    counts drops by reason for the run summary.

    Side effect: every candidate that passes hard filters is added to
    ``seen_urls`` and ``seen_domains`` (so caller can persist after the
    run regardless of score).
    """
    excluded = excluded_domains if excluded_domains is not None else _load_excluded_domains()
    stats = {
        "total": len(candidates),
        "seen": 0,
        "excluded": 0,
        "stale": 0,
        "non_english": 0,
        "unreachable": 0,
        "empty": 0,
        "below_threshold": 0,
        "qualified": 0,
    }
    qualified: list[dict[str, Any]] = []

    for c in candidates:
        url = c.get("url")
        domain = (c.get("domain") or host_of(url or "")).lower()
        title = c.get("title") or ""
        desc = c.get("description") or ""

        if not url or not domain:
            stats["empty"] += 1
            continue
        if not title or not desc:
            stats["empty"] += 1
            continue

        if url in seen_urls:
            stats["seen"] += 1
            continue
        if domain in seen_domains:
            stats["seen"] += 1
            continue
        if domain in excluded:
            stats["excluded"] += 1
            continue
        if not _is_recent_enough(c.get("published_date"), max_age_months):
            stats["stale"] += 1
            continue
        if not _looks_english(title, desc):
            stats["non_english"] += 1
            continue
        if reachability_check and not _is_reachable(url):
            stats["unreachable"] += 1
            continue

        # Past every hard filter — record so we never reconsider it.
        seen_urls.add(url)
        seen_domains.add(domain)

        c["lead_score"] = score(c)
        if c["lead_score"] < min_score:
            stats["below_threshold"] += 1
            continue

        qualified.append(c)
        stats["qualified"] += 1

    log(
        "qualify: "
        + "  ".join(f"{k}={v}" for k, v in stats.items())
    )
    return qualified, stats
