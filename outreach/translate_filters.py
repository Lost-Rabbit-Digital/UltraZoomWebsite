"""Plain-English seed → Apollo.io People Search filter object via Claude.

Apollo's UI offers a guided filter builder; the API accepts the same
shape directly but expects the caller to know which array names map to
which concept (``person_titles``, ``person_seniorities``,
``q_organization_keyword_tags``, etc.). Claude Haiku does that mapping
for us so the seed file can stay in plain English.

Two prompts ship under ``outreach/prompts/``:
  uz_filters.md  — image-heavy B2B power-users (workers reviewing lots
                   of detailed photos in a browser as part of their day).
  hb_filters.md  — pen-test + MSSP decision-makers.

The prompt instructs Claude to return only a JSON object. We strip
common decorations (markdown fences, leading "json", surrounding
quotes), parse the JSON, and whitelist the keys before passing them to
Apollo so a prompt mis-fire can't smuggle in unsupported parameters.

Filter cache key: ``(lane, seed)`` for 7 days. Each unique seed maps to
a single ~150-token request, so the filter-cache hit rate dominates the
cost of running the same seed across multiple workflow_dispatch runs.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .cache import JsonCache
from .config import CACHE_DIR, PROMPTS_DIR
from .enrich_personalize import MODEL_IDS, _call_anthropic
from .util import log

FILTER_CACHE = CACHE_DIR / "apollo_filter_cache.json"
FILTER_TTL_DAYS = 7

# Whitelist of filter keys we forward to Apollo. Anything else is
# stripped silently so a prompt drift doesn't waste credits on a
# malformed filter.
ALLOWED_FILTER_KEYS = {
    "person_titles",
    "person_not_titles",
    "person_seniorities",
    "person_locations",
    "person_not_locations",
    "person_past_titles",
    "q_keywords",
    "organization_locations",
    "organization_not_locations",
    "organization_num_employees_ranges",
    "organization_industry_tag_ids",
    "q_organization_keyword_tags",
    "q_organization_name",
    "contact_email_status",
}

# Apollo accepts a small enum for seniorities. Anything else gets dropped
# instead of risking an API rejection that would tank the run.
ALLOWED_SENIORITIES = {
    "owner",
    "founder",
    "c_suite",
    "partner",
    "vp",
    "head",
    "director",
    "manager",
    "senior",
    "entry",
    "intern",
}

ALLOWED_EMAIL_STATUSES = {"verified", "likely_to_engage", "unverified", "unavailable"}

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
    s = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", s, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    if s.startswith("{") and s.endswith("}"):
        return s
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
    """Drop unknown keys, normalize enum-valued fields, and force the
    ``contact_email_status`` floor of ``verified`` so we never spend on
    rows whose emails Apollo couldn't confirm.
    """
    clean: dict[str, Any] = {}
    for key, value in filters.items():
        if key not in ALLOWED_FILTER_KEYS:
            continue
        if key == "person_seniorities" and isinstance(value, list):
            value = [v for v in value if isinstance(v, str) and v.lower() in ALLOWED_SENIORITIES]
            if not value:
                continue
        if key == "contact_email_status" and isinstance(value, list):
            value = [v for v in value if isinstance(v, str) and v.lower() in ALLOWED_EMAIL_STATUSES]
            if not value:
                continue
        clean[key] = value
    clean.setdefault("contact_email_status", ["verified"])
    return clean


def translate(
    *,
    lane: str,
    seed: str,
    api_key: str,
    model: str = "haiku",
    cache: JsonCache | None = None,
) -> dict[str, Any] | None:
    """Return an Apollo filter dict for ``seed``, or ``None`` on parse failure.

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
    if not filters or not any(k for k in filters if k != "contact_email_status"):
        log(f"  filter parse: no recognized targeting keys in {list(parsed)!r}")
        cache.set(cache_key, {})
        return None

    cache.set(cache_key, filters)
    return filters
