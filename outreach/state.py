"""Persistent dedupe state.

``seen_urls.json`` and ``seen_domains.json`` live in ``state/`` and are
committed back to the repo from CI. Once a URL or domain lands in here we
never re-discover or re-outreach it — even if it scored too low to stage,
we don't want to re-process it on a subsequent run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .config import SEEN_DOMAINS_PATH, SEEN_URLS_PATH


def _load_set(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return set()
    if isinstance(data, list):
        return set(data)
    if isinstance(data, dict):
        return set(data.keys())
    return set()


def _save_set(path: Path, values: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sorted(values), indent=2))


def load_seen() -> tuple[set[str], set[str]]:
    return _load_set(SEEN_URLS_PATH), _load_set(SEEN_DOMAINS_PATH)


def save_seen(urls: Iterable[str], domains: Iterable[str]) -> None:
    _save_set(SEEN_URLS_PATH, set(urls))
    _save_set(SEEN_DOMAINS_PATH, set(domains))
