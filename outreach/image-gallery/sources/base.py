"""Shared types for discovery sources."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Candidate:
    """A single image opportunity surfaced by a Stage 1 adapter.

    ``image_url`` must point to the raw image bytes (jpg/png/webp). If the
    source returns an HTML page or an album, the adapter is responsible for
    resolving it to a single image URL before yielding the Candidate.
    """
    source: str                 # reddit | commons | nasa | exa
    source_id: str              # stable id within that source
    image_url: str
    source_url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    score: Optional[int] = None
    published_at: Optional[str] = None
    metadata: dict = field(default_factory=dict)
