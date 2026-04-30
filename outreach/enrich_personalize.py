"""Claude-powered personalized email drafting.

Per lead, generates a JSON payload ``{"subject": ..., "body": ...}`` for
one touch (1 or 2) of a campaign. The system prompt is the campaign
brief excerpt plus the touch's reference template, and is sent with
``cache_control`` so successive leads in the same batch only pay the
prompt-caching write cost on the first call.

The output is then validated against the campaign's rules (banned
words, required merge tags, length, em-dashes, sycophancy). One strict
retry on failure; two failures drop the candidate so MailMeteor never
sees a junk row.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from typing import Any

from .campaign_config import CampaignConfig
from .config import (
    PERSONALIZATION_BODY_MIN_WORDS,
    PERSONALIZATION_SUBJECT_MAX_WORDS,
)
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


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

_SYSTEM_HEADER = """\
You are drafting a single cold-email touch for a Lost Rabbit Digital outreach
campaign. Your job is to produce a JSON object with two fields, ``subject``
and ``body``, personalized to the lead's data the user message will give you.

You are NOT writing marketing copy from scratch. The campaign brief below
defines the voice, the structure, and the required merge tags. Your room to
maneuver is the opening hook tied to the lead's specific signals (city,
company, role, industry, keywords) and the phrasing of the value prop.

Hard rules — violations cause your draft to be rejected:
- No em-dashes. Use periods or commas instead.
- No sycophancy. Do not open with "I love", "great article", "really
  enjoyed", or similar.
- No vendor buzzwords. The campaign config below lists banned phrases.
- Subject line: at most {subject_max} words. No clickbait, no all-caps.
- Body: between {body_min} and {body_max} words. Plain prose. No bullet
  lists, no markdown. End with the signoff exactly as the reference shows.
- Output only the JSON object. No preamble, no commentary, no code fences.
"""


def _build_system_prompt(campaign: CampaignConfig, *, touch: int) -> str:
    """Assemble the cached system-prompt text for one (campaign, touch).

    The same prompt is reused for every lead in a batch, so prompt
    caching pays off after the first call. Caching is requested by the
    HTTP layer via ``cache_control``; this function only assembles the
    text.
    """
    prompt_path = campaign.prompt_t1 if touch == 1 else campaign.prompt_t2
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"campaign prompt missing for {campaign.name} touch {touch}: "
            f"{prompt_path}"
        )
    reference = prompt_path.read_text()

    required_tokens = (
        campaign.required_tokens_t1 if touch == 1 else campaign.required_tokens_t2
    )
    banned = campaign.all_banned_words()

    pieces = [
        _SYSTEM_HEADER.format(
            subject_max=PERSONALIZATION_SUBJECT_MAX_WORDS,
            body_min=PERSONALIZATION_BODY_MIN_WORDS,
            body_max=campaign.max_body_words,
        ),
        f"\n## Campaign\n\n{campaign.name} — Touch {touch}\n",
        f"\n## Sender voice\n\n{campaign.voice_summary}\n",
        f"\n## Recipient persona\n\n{campaign.persona_summary}\n",
        f"\n## Touch reference template + tone notes\n\n{reference}\n",
    ]
    if required_tokens:
        listed = "\n".join(f"- `{t}`" for t in required_tokens)
        pieces.append(
            "\n## Required body tokens (must appear verbatim)\n\n"
            f"{listed}\n\n"
            "Embed each of these strings somewhere in the body, exactly as "
            "written. The literal-string merge tags (anything wrapped in "
            "double curly braces) are placeholders MailMeteor will fill at "
            "send time. Do not invent a value or remove the braces.\n"
        )
    if banned:
        listed = ", ".join(f"`{w}`" for w in banned)
        pieces.append(
            "\n## Banned words/phrases (case-insensitive)\n\n"
            f"{listed}\n\n"
            "If a banned word is unavoidable to discuss the topic, rephrase "
            "the topic.\n"
        )
    pieces.append(
        "\n## Output schema\n\n"
        'Return exactly:\n\n```json\n{"subject": "...", "body": "..."}\n```\n\n'
        "No other keys. No comments. No code fence in the actual output — "
        "just the JSON.\n"
    )
    return "".join(pieces)


def _build_user_message(lead: dict[str, Any]) -> str:
    """Render one lead's signals as a compact prompt-friendly block."""
    fields = [
        ("First name", lead.get("first_name", "")),
        ("Last name", lead.get("last_name", "")),
        ("Title", lead.get("editor_title", "")),
        ("Company", lead.get("company", "")),
        ("Domain", lead.get("domain", "")),
        ("City", lead.get("city", "")),
        ("State", lead.get("state", "")),
        ("Industry", lead.get("industry", "")),
        ("Keywords", lead.get("keywords", "")),
    ]
    rendered = "\n".join(f"- {label}: {value}" for label, value in fields if value)
    return f"Lead data:\n\n{rendered}\n\nDraft the JSON now."


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def _call_anthropic(
    *,
    api_key: str,
    model_id: str,
    system_text: str,
    user_text: str,
    max_tokens: int,
) -> str:
    """POST to /v1/messages with prompt caching on the system block.

    Returns the raw text of the first text block in the response.
    """
    body = {
        "model": model_id,
        "max_tokens": max_tokens,
        "system": [
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        "messages": [{"role": "user", "content": user_text}],
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


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _parse_json(raw: str) -> dict[str, str] | None:
    """Salvage a JSON object out of Claude's response. Tolerates code
    fences, language tags, and leading commentary even though the prompt
    forbids them.
    """
    s = raw.strip()
    # Locate the outermost ``{...}``. The brace search reliably skips
    # past any leading commentary, opening code fence, or language tag
    # without us having to special-case each variant.
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    blob = s[start : end + 1]
    try:
        # ``strict=False`` allows literal newlines inside string values.
        # Claude routinely emits multi-line bodies with real ``\n``
        # characters rather than JSON ``\\n`` escapes, and rejecting those
        # over a pedantic-compliance check would cost us a free retry.
        parsed = json.loads(blob, strict=False)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    subject = parsed.get("subject")
    body = parsed.get("body")
    if not isinstance(subject, str) or not isinstance(body, str):
        return None
    return {"subject": subject.strip(), "body": body.strip()}


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def validate(
    drafted: dict[str, str],
    *,
    campaign: CampaignConfig,
    touch: int,
) -> tuple[bool, str]:
    """Return ``(ok, reason)``. ``reason`` is empty when ``ok`` is True."""
    subject = drafted.get("subject", "")
    body = drafted.get("body", "")

    if not subject:
        return False, "empty subject"
    if not body:
        return False, "empty body"

    if "—" in body or "–" in body or "—" in subject or "–" in subject:
        return False, "em dash"

    sub_words = _word_count(subject)
    if sub_words > PERSONALIZATION_SUBJECT_MAX_WORDS:
        return False, f"subject too long ({sub_words} words)"

    body_words = _word_count(body)
    if body_words < PERSONALIZATION_BODY_MIN_WORDS:
        return False, f"body too short ({body_words} words)"
    if body_words > campaign.max_body_words:
        return False, f"body too long ({body_words} words)"

    if SYCOPHANCY_RE.search(body):
        return False, "sycophantic opener"

    banned_lower = [w.lower() for w in campaign.all_banned_words()]
    body_lower = body.lower()
    for w in banned_lower:
        if w in body_lower:
            return False, f"banned phrase: {w!r}"

    required = (
        campaign.required_tokens_t1 if touch == 1 else campaign.required_tokens_t2
    )
    for token in required:
        if token not in body:
            return False, f"missing required token: {token!r}"

    return True, ""


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def personalize(
    lead: dict[str, Any],
    *,
    campaign: CampaignConfig,
    touch: int,
    api_key: str,
    model: str = "haiku",
) -> tuple[dict[str, str] | None, str]:
    """Generate a personalized ``{"subject": ..., "body": ...}`` for one
    touch of one lead. Returns ``(payload, "")`` on success or
    ``(None, reason)`` after the strict retry also fails.
    """
    model_id = MODEL_IDS.get(model, MODEL_IDS["haiku"])
    system_text = _build_system_prompt(campaign, touch=touch)
    user_text = _build_user_message(lead)

    raw = _call_anthropic(
        api_key=api_key,
        model_id=model_id,
        system_text=system_text,
        user_text=user_text,
        max_tokens=600,
    )
    drafted = _parse_json(raw)
    if drafted is not None:
        ok, reason = validate(drafted, campaign=campaign, touch=touch)
        if ok:
            return drafted, ""
    else:
        reason = "unparseable JSON"

    log(
        f"  personalization failed ({reason}), retrying strict — "
        f"{lead.get('editor_email')} touch{touch}"
    )
    strict_user = (
        user_text
        + "\n\nYour previous attempt failed validation: "
        + reason
        + ". Output ONLY the JSON object, no preamble, no code fence. "
        + "Re-check the required tokens and banned words before responding."
    )
    raw = _call_anthropic(
        api_key=api_key,
        model_id=model_id,
        system_text=system_text,
        user_text=strict_user,
        max_tokens=600,
    )
    drafted = _parse_json(raw)
    if drafted is None:
        return None, "unparseable JSON (retry)"
    ok, reason = validate(drafted, campaign=campaign, touch=touch)
    if ok:
        return drafted, ""
    return None, reason
