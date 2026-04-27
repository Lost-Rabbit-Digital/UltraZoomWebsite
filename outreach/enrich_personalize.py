"""Claude-powered personalized opener generation.

Renders ``prompts/personalization.md`` with the post's title, description,
and domain, calls the Anthropic Messages API directly via stdlib, and
validates the output against the standing-preference rules (no em dashes,
no sycophancy, ≤25 words, etc.). One retry with a stricter prompt on
validation failure; if that also fails, the candidate is dropped with
status ``personalization_failed``.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from .config import PERSONALIZATION_HARD_MAX_WORDS, PERSONALIZATION_MAX_WORDS, PROMPTS_DIR
from .util import log

ANTHROPIC_BASE = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
MAX_ATTEMPTS = 4

MODEL_IDS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}

# Sycophantic openers to reject. Matched at the start of the sentence,
# case-insensitive.
SYCOPHANTIC_PATTERNS = [
    r"^i\s+love",
    r"^i\s+loved",
    r"^great\s+(post|article|piece|read)",
    r"^amazing\s+(post|article|piece|read|work)",
    r"^awesome\s+(post|article|piece|read|work)",
    r"^what\s+a\s+(wonderful|great|fantastic)",
    r"^this\s+is\s+(fantastic|amazing|wonderful|great)",
    r"^really\s+enjoyed",
    r"^just\s+wanted\s+to\s+say",
]
SYCOPHANCY_RE = re.compile("|".join(SYCOPHANTIC_PATTERNS), re.IGNORECASE)
BANNED_WORDS_RE = re.compile(r"\b(stumbled|amazing)\b", re.IGNORECASE)


# Buckets with their own tuned personalization prompt. Buckets not listed
# here fall back to ``personalization.md``.
BUCKET_PROMPTS: dict[str, str] = {
    "E": "personalization-genealogy.md",
    "F": "personalization-a11y.md",
}


def _load_prompt(bucket: str | None = None) -> str:
    filename = BUCKET_PROMPTS.get(bucket or "", "personalization.md")
    path = PROMPTS_DIR / filename
    if not path.exists():
        path = PROMPTS_DIR / "personalization.md"
    return path.read_text()


def _render(template: str, *, title: str, description: str, domain: str) -> str:
    return (
        template.replace("{title}", title)
        .replace("{description}", description)
        .replace("{domain}", domain)
    )


def _call_anthropic(api_key: str, model_id: str, prompt: str, *, max_tokens: int = 200) -> str:
    body = {
        "model": model_id,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        req = urllib.request.Request(
            ANTHROPIC_BASE,
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": ANTHROPIC_VERSION,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                payload: dict[str, Any] = json.loads(resp.read().decode("utf-8"))
                blocks = payload.get("content") or []
                for block in blocks:
                    if block.get("type") == "text":
                        return (block.get("text") or "").strip()
                return ""
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in RETRY_STATUSES and attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  claude retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — HTTP {e.code}")
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError as e:
            last_err = e
            if attempt < MAX_ATTEMPTS:
                wait = 2**attempt
                log(f"  claude retry {attempt}/{MAX_ATTEMPTS - 1} after {wait}s — {e.reason}")
                time.sleep(wait)
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("claude: exhausted attempts")


def _strip(text: str) -> str:
    s = text.strip()
    # Strip surrounding quotes Claude sometimes adds despite instructions.
    if len(s) >= 2 and s[0] in {'"', "'", "“", "‘"} and s[-1] in {'"', "'", "”", "’"}:
        s = s[1:-1].strip()
    # Take the first sentence only.
    parts = re.split(r"(?<=[.!?])\s+", s)
    return parts[0].strip() if parts else s


def validate(opener: str) -> tuple[bool, str]:
    """Return ``(ok, reason)``. Reason is empty when ``ok`` is True."""
    if not opener:
        return False, "empty"
    if "—" in opener or "–" in opener:
        return False, "em dash"
    words = opener.split()
    if len(words) > PERSONALIZATION_HARD_MAX_WORDS:
        return False, f"too long ({len(words)} words)"
    if SYCOPHANCY_RE.search(opener):
        return False, "sycophantic opener"
    if BANNED_WORDS_RE.search(opener):
        return False, "banned word"
    if not re.search(r"[.!?]$", opener):
        return False, "missing terminal punctuation"
    return True, ""


def personalize(
    candidate: dict[str, Any],
    *,
    api_key: str,
    model: str = "haiku",
) -> tuple[str, str]:
    """Return ``(opener, error)``. ``error`` is empty on success."""
    model_id = MODEL_IDS.get(model, MODEL_IDS["haiku"])
    base_prompt = _render(
        _load_prompt(candidate.get("bucket")),
        title=candidate.get("title", ""),
        description=candidate.get("description", ""),
        domain=candidate.get("domain", ""),
    )

    raw = _call_anthropic(api_key, model_id, base_prompt)
    opener = _strip(raw)
    ok, reason = validate(opener)
    if ok:
        return opener, ""

    log(f"  personalization failed ({reason}), retrying strict — {candidate.get('domain')}")
    strict_prompt = (
        base_prompt
        + "\n\nYour previous attempt failed validation: "
        + reason
        + ". Try again. "
        + f"Stay under {PERSONALIZATION_MAX_WORDS} words. No em dashes, no sycophancy, "
        "no quotes, no preamble. Output only the sentence."
    )
    raw = _call_anthropic(api_key, model_id, strict_prompt)
    opener = _strip(raw)
    ok, reason = validate(opener)
    if ok:
        return opener, ""
    return "", reason
