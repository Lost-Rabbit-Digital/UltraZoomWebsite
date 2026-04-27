"""Simple file-backed JSON cache.

Used by every external API client to avoid re-billing when reruns hit the
same query. Each cache file is a flat dict keyed by a stable string. TTLs
are evaluated lazily on read.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class JsonCache:
    def __init__(self, path: Path, *, ttl_days: int | None = None) -> None:
        self.path = path
        self.ttl_seconds = ttl_days * 86400 if ttl_days else None
        self._data: dict[str, dict[str, Any]] | None = None

    def _load(self) -> dict[str, dict[str, Any]]:
        if self._data is not None:
            return self._data
        if not self.path.exists():
            self._data = {}
            return self._data
        try:
            self._data = json.loads(self.path.read_text())
        except json.JSONDecodeError:
            self._data = {}
        return self._data

    def get(self, key: str) -> Any | None:
        entry = self._load().get(key)
        if not entry:
            return None
        if self.ttl_seconds is not None:
            age = time.time() - entry.get("ts", 0)
            if age > self.ttl_seconds:
                return None
        return entry.get("value")

    def set(self, key: str, value: Any) -> None:
        data = self._load()
        data[key] = {"ts": time.time(), "value": value}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, indent=2, default=str))
