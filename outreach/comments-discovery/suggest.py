"""Generates a suggested comment for a candidate article using the
Anthropic API. The prompt is deliberately conservative: the goal is a
thoughtful first draft that a human will edit, not a finished post.

Cost note: input ~600 tokens, output ~200 tokens per call. With Claude
Sonnet pricing (~$3/M in, $15/M out) you're at ~$0.005 per suggestion.
At 100 candidates that's $0.50 — negligible for the workflow.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import anthropic

MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are helping a human draft a comment to leave on a military or aerospace blog post. The human owns Ultra Zoom, a browser extension that lets people zoom into images on web pages with AI enhancement. Their goal is to share a genuine zoom-and-enhance result on the article's imagery as a useful contribution to the comment thread.

Hard rules for the suggested comment:
1. The human will actually run Ultra Zoom on the article's images before posting, so reference what they might find ("the tail section", "the area near the canopy") rather than fabricating specifics.
2. Do NOT include URLs, do NOT include "check out my extension" or any promotional language. The human's username on the comment is their only attribution.
3. Mention "Ultra Zoom" by name at most once, and only in a natural aside ("ran it through Ultra Zoom") — never as a recommendation.
4. Tone: knowledgeable enthusiast, not marketer. Match the register of a typical commenter on that kind of blog.
5. Length: 2-4 sentences. Real comments are short.
6. If the article's subject matter doesn't actually contain imagery worth zooming on (opinion piece, text-heavy news), output exactly: SKIP

Return only the comment text (or SKIP). No preamble, no quotes around it, no signature."""


@dataclass
class Suggestion:
    text: Optional[str]      # None if SKIP
    model: str
    cost_usd: float
    skip: bool


def suggest_comment(
    article_title: str,
    excerpt: str,
    header_caption: Optional[str],
    zoom_signal: str,
    *,
    client: Optional[anthropic.Anthropic] = None,
) -> Suggestion:
    client = client or anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    user_msg = f"""Article title: {article_title}

Header image caption: {header_caption or '(none)'}

Article excerpt: {excerpt}

Zoom-relevance categories detected: {zoom_signal or '(none)'}

Draft a comment per the rules."""

    resp = client.messages.create(
        model=MODEL,
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )

    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    skip = text.upper().startswith("SKIP")

    # Sonnet 4.5 pricing as of 2026 - update if Anthropic changes it
    in_cost = resp.usage.input_tokens / 1_000_000 * 3.0
    out_cost = resp.usage.output_tokens / 1_000_000 * 15.0
    cost = round(in_cost + out_cost, 5)

    return Suggestion(
        text=None if skip else text,
        model=MODEL,
        cost_usd=cost,
        skip=skip,
    )
