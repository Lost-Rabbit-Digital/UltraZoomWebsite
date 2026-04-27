"""Tiny shared helpers."""

from __future__ import annotations

import sys
from datetime import datetime
from urllib.parse import urlparse


def log(msg: str) -> None:
    """Stderr-only logger so JSON output on stdout (when we add any) stays
    machine-readable.
    """
    print(msg, file=sys.stderr, flush=True)


def host_of(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host.lower().removeprefix("www.")


def to_iso_date(value: str) -> str:
    """Normalize provider-reported publish dates to ``YYYY-MM-DD``.

    Exa returns ISO-8601 already; Brave's ``page_age`` can be ISO, a long-
    form date, or relative phrases like "3 days ago". Returns "" when the
    input is unparseable.
    """
    if not value:
        return ""
    s = str(value).strip()
    if not s:
        return ""

    # ISO prefix.
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        head = s[:10]
        try:
            datetime.strptime(head, "%Y-%m-%d")
            return head
        except ValueError:
            pass

    # Relative phrase: "3 days ago".
    parts = s.lower().split()
    if len(parts) >= 3 and parts[-1] == "ago":
        try:
            n = int(parts[0])
        except ValueError:
            n = -1
        unit = parts[1].rstrip("s")
        if n >= 0:
            now = datetime.utcnow()
            try:
                if unit == "second":
                    delta_seconds = n
                elif unit == "minute":
                    delta_seconds = n * 60
                elif unit == "hour":
                    delta_seconds = n * 3600
                elif unit == "day":
                    delta_seconds = n * 86400
                elif unit == "week":
                    delta_seconds = n * 7 * 86400
                elif unit == "month":
                    delta_seconds = n * 30 * 86400
                elif unit == "year":
                    delta_seconds = n * 365 * 86400
                else:
                    delta_seconds = None
                if delta_seconds is not None:
                    from datetime import timedelta

                    return (now - timedelta(seconds=delta_seconds)).date().isoformat()
            except (TypeError, ValueError):
                pass

    # Long-form fallback.
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return ""


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def today_iso() -> str:
    return datetime.utcnow().date().isoformat()
