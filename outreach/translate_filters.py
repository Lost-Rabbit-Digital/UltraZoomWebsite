"""Plain-English seed → Wiza filter object via Claude Haiku.

Wiza's Smart Search (the UI feature that translates a sentence into a
filter object) is not exposed via API, so we do that translation
ourselves. Claude Haiku is cheap and deterministic enough that the
filter-cache hit rate dominates the cost: each unique seed maps to a
single ~150-token request that we cache for 7 days.

Two prompts ship under outreach/prompts/:
  uz_filters.md  — power-user discovery (people in image-heavy niches)
  hb_filters.md  — security decision-maker discovery (MSSPs, pentest, etc.)

The prompt instructs Claude to return only a JSON object. We strip
common decorations (markdown fences, leading "json", surrounding quotes)
and json.loads it. Parse failures are surfaced — they nearly always
mean the prompt itself needs adjustment, not the seed.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .cache import JsonCache
from .config import CACHE_DIR, PROMPTS_DIR
from .enrich_personalize import MODEL_IDS, _call_anthropic
from .util import log

FILTER_CACHE = CACHE_DIR / "wiza_filter_cache.json"
FILTER_TTL_DAYS = 7

# Whitelist of filter keys we accept from Claude. Extra keys are stripped
# before sending to Wiza so a prompt mis-fire can't smuggle in something
# weird that wastes credits on a broken filter.
ALLOWED_FILTER_KEYS = {
    "first_name",
    "last_name",
    "job_title",
    "job_title_level",
    "job_role",
    "job_sub_role",
    "location",
    "skill",
    "school",
    "major",
    "linkedin_slug",
    "job_company",
    "past_company",
    "company_location",
    "company_industry",
    "company_size",
    "company_annual_growth",
    "department_size",
    "company_type",
    "company_summary",
    "year_founded_start",
    "year_founded_end",
    "funding_date",
    "funding_min",
    "funding_max",
    "last_funding_min",
    "last_funding_max",
    "funding_stage",
    "funding_type",
}

PROMPT_FILES = {
    "uz": "uz_filters.md",
    "hb": "hb_filters.md",
}


def _load_prompt(lane: str) -> str:
    filename = PROMPT_FILES.get(lane)
    if not filename:
        raise ValueError(f"unknown lane {lane!r}; expected one of {sorted(PROMPT_FILES)}")
    return (PROMPTS_DIR / filename).read_text()


def _extract_json(text: str) -> str:
    """Strip markdown fences and leading 'json' label that Claude
    sometimes adds despite the prompt's instructions. Falls back to the
    first balanced ``{...}`` block.
    """
    s = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    if s.startswith("{") and s.endswith("}"):
        return s
    # Last-resort: pull the first balanced object out of arbitrary text.
    start = s.find("{")
    if start < 0:
        return s
    depth = 0
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return s[start:]


def _sanitize(filters: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in filters.items() if k in ALLOWED_FILTER_KEYS}


def translate(
    *,
    lane: str,
    seed: str,
    api_key: str,
    model: str = "haiku",
    cache: JsonCache | None = None,
) -> dict[str, Any] | None:
    """Return a Wiza filter dict for ``seed``, or ``None`` on parse failure.

    ``lane`` selects the prompt file (``uz`` or ``hb``).
    Cached for ``FILTER_TTL_DAYS`` keyed by ``(lane, seed)``.
    """
    cache = cache or JsonCache(FILTER_CACHE, ttl_days=FILTER_TTL_DAYS)
    cache_key = f"{lane}|{seed}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached or None

    template = _load_prompt(lane)
    prompt = template.replace("{seed}", seed.strip())
    raw = _call_anthropic(api_key, MODEL_IDS.get(model, MODEL_IDS["haiku"]), prompt, max_tokens=400)
    json_text = _extract_json(raw)

    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as e:
        log(f"  filter parse error: {e}; raw: {raw[:200]!r}")
        cache.set(cache_key, {})
        return None

    if not isinstance(parsed, dict):
        log(f"  filter parse: expected object, got {type(parsed).__name__}")
        cache.set(cache_key, {})
        return None

    filters = _sanitize(parsed)
    if not filters:
        log(f"  filter parse: no recognized keys in {list(parsed)!r}")
        cache.set(cache_key, {})
        return None

    cache.set(cache_key, filters)
    return filters
