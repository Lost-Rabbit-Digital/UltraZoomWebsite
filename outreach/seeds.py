"""Seed keyword strategy.

Seeds are grouped into rotating buckets so each cron picks a different
angle. State lives in ``state/seed_rotation_state.json`` and is committed
back from CI so rotation persists across runs.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .config import SEED_ROTATION_PATH

# ``[year]`` is templated at runtime to current year and current year - 1.
BUCKETS: dict[str, list[str]] = {
    "A": [
        "best chrome extensions for [year]",
        "best firefox extensions for productivity",
        "must-have browser extensions for designers",
        "chrome extensions for accessibility",
        "privacy-focused chrome extensions",
        "chrome extensions for image-heavy workflows",
        "top firefox add-ons [year]",
        "essential browser extensions for ux designers",
        "best browser extensions for power users [year]",
        "underrated chrome extensions [year]",
        "chrome extensions for researchers",
        "chrome extensions for writers and editors",
    ],
    "B": [
        "tools for inspecting design details on websites",
        "how to zoom in on websites",
        "chrome extensions for low vision users",
        "accessibility tools for web designers",
        "tools for analyzing images on websites",
        "browser tools for ecommerce product photography",
        "how to magnify images in browser",
        "tools for examining product photos online",
        "browser zoom tools for genealogy research",
        "browser tools for inspecting fine art online",
    ],
    "C": [
        "web designer toolbox",
        "digital accessibility resources",
        "ecommerce product page audit tools",
        "ux research browser tools",
        "visual designer toolkit [year]",
        "front end developer toolbox",
        "tools for visual qa on websites",
    ],
    "D": [
        "ultimate resource list for designers",
        "useful websites for developers",
        "tools every designer should bookmark",
        "best free design tools roundup",
        "directory of browser tools for creatives",
        "curated list of accessibility resources",
    ],
}

BUCKET_ORDER = ["A", "B", "C", "D"]


@dataclass
class SeedSelection:
    bucket: str
    seeds: list[str]


def _expand_year(seed: str, year: int) -> list[str]:
    """Expand ``[year]`` to the current year and the previous year. Seeds
    without ``[year]`` pass through unchanged.
    """
    if "[year]" not in seed:
        return [seed]
    return [seed.replace("[year]", str(year)), seed.replace("[year]", str(year - 1))]


def expand_bucket(bucket: str, *, year: int | None = None) -> list[str]:
    if bucket not in BUCKETS:
        raise ValueError(f"unknown bucket: {bucket}")
    y = year or datetime.utcnow().year
    out: list[str] = []
    for raw in BUCKETS[bucket]:
        out.extend(_expand_year(raw, y))
    return out


def _load_state(path: Path = SEED_ROTATION_PATH) -> dict:
    if not path.exists():
        return {"last_bucket": None, "history": []}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"last_bucket": None, "history": []}


def _save_state(state: dict, path: Path = SEED_ROTATION_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2))


def _next_bucket(last: str | None) -> str:
    """Round-robin to the next bucket, never repeating the previous one
    (the audit checklist forbids running the same bucket two days in a row).
    """
    if last is None or last not in BUCKET_ORDER:
        return BUCKET_ORDER[0]
    idx = (BUCKET_ORDER.index(last) + 1) % len(BUCKET_ORDER)
    return BUCKET_ORDER[idx]


def select_for_run(
    *,
    bucket: str | None = None,
    sample_size: int = 6,
    rng: random.Random | None = None,
    persist: bool = True,
    state_path: Path = SEED_ROTATION_PATH,
) -> SeedSelection:
    """Pick the bucket for this run, sample 5-8 seeds from it.

    ``bucket`` lets a caller force a specific bucket (the ``--bucket A``
    CLI flag). ``persist=False`` skips the state write so dry runs don't
    advance the rotation.
    """
    state = _load_state(state_path)
    chosen = bucket if bucket in BUCKETS else _next_bucket(state.get("last_bucket"))
    seeds = expand_bucket(chosen)
    rng = rng or random.Random()
    sample = rng.sample(seeds, k=min(sample_size, len(seeds)))

    if persist:
        history = state.get("history", [])
        history.append(
            {"bucket": chosen, "ran_at": datetime.utcnow().isoformat(timespec="seconds")}
        )
        # Keep last 30 entries — enough to debug rotation drift, small
        # enough that the JSON file stays readable in a code review.
        state["last_bucket"] = chosen
        state["history"] = history[-30:]
        _save_state(state, state_path)

    return SeedSelection(bucket=chosen, seeds=sample)
