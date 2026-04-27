"""Find recent Reddit questions that Ultra Zoom answers, draft replies.

Searches Reddit (via Exa, with a recency filter) for posts where someone
is asking for what Ultra Zoom solves, then asks Claude to draft a helpful
reply that mentions Ultra Zoom as one option among others. Output is a
markdown file in ``outreach/reddit_queue/{date}.md``.

The replies are *suggested*: a human reviews, edits, and posts them
manually from a real account with comment history. We do not automate
posting — Reddit's anti-spam systems penalize per-account patterns and
one human poster outperforms a script every time.

Usage:
    python -m outreach.find_reddit_questions [--days 7] [--per-query 5]
                                             [--icp genealogy,a11y]
                                             [--out path] [--dry-run]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from . import discover_exa, enrich_personalize
from .util import log, today_iso

DEFAULT_OUT_DIR = Path("outreach/reddit_queue")
DEFAULT_DAYS = 7
DEFAULT_PER_QUERY = 5

# High-intent question patterns by ICP. Each query is a real way someone
# might phrase the pain Ultra Zoom solves. Exa's neural retrieval handles
# the rest, so a handful of well-shaped queries cover a lot of variants.
ICP_QUERIES: dict[str, list[str]] = {
    "genealogy": [
        "how to zoom into Ancestry images",
        "FamilySearch scan too pixelated to read",
        "browser extension to read scanned census records",
        "tool to enlarge old newspaper scans for genealogy",
        "reading faded handwriting on scanned wills",
        "magnify scanned documents in browser",
    ],
    "a11y": [
        "best chrome extension for low vision web browsing",
        "extension to make text bigger than browser zoom max",
        "low vision browser tools recommendations",
        "magnifier extension that doesn't blur text",
        "browsing the web with macular degeneration",
        "screen magnifier alternatives for chrome",
    ],
    "resellers": [
        "chrome extension to inspect product photos for fakes",
        "how to zoom into eBay listing images",
        "tool to examine StockX or GOAT photos in detail",
        "extension to magnify Etsy product images",
        "spotting counterfeit details in online listings",
    ],
}


def _exa_search_reddit(
    *,
    api_key: str,
    query: str,
    start_date: str,
    num_results: int,
) -> list[dict[str, Any]]:
    """Hit Exa /search restricted to reddit.com with a recency floor."""
    body = {
        "query": query,
        "numResults": min(num_results, 10),
        "type": "auto",
        "includeDomains": ["reddit.com"],
        "startPublishedDate": start_date,
        "contents": {"text": {"maxCharacters": 600}},
    }
    # Reuse discover_exa._call to inherit its retry + auth handling.
    resp = discover_exa._call("/search", body, api_key)
    return resp.get("results", []) or []


REPLY_PROMPT = """You are drafting a Reddit reply for a human to review and post manually.

Subreddit: {subreddit}
Question title: {title}
Question excerpt: {excerpt}

Write a helpful, conversational reply (80-150 words) that:

1. Actually answers the question first. Be specific and useful even if Ultra Zoom is not the right answer.
2. Mentions 2-3 options total. If Ultra Zoom genuinely helps with what the OP described, include it as ONE option (free Chrome extension, $4/mo for advanced features like position memory and per-site presets). Always include at least one non-Ultra-Zoom alternative (e.g. browser DevTools zoom, downloading the source image, OS magnifier, a different extension you know of) — recommendations that pretend the OP's only option is your tool read as spam.
3. If Ultra Zoom does NOT actually fit the question, say so and recommend the right thing. Do not force a mention.
4. Use plain Reddit-comment voice. No bullet lists, no headers, no marketing words. Contractions are fine. No em dashes.
5. Do not start with "Hey OP" or "Great question". Do not sign off. Do not include affiliate disclosure (the human poster handles that).

Output only the reply text. No preamble, no markdown headers, no quotes around the reply."""


def _draft_reply(
    *,
    api_key: str,
    model_id: str,
    subreddit: str,
    title: str,
    excerpt: str,
) -> str:
    prompt = (
        REPLY_PROMPT.replace("{subreddit}", subreddit)
        .replace("{title}", title)
        .replace("{excerpt}", excerpt[:600])
    )
    return enrich_personalize._call_anthropic(api_key, model_id, prompt, max_tokens=400).strip()


def _subreddit_of(url: str) -> str:
    # https://reddit.com/r/Genealogy/comments/abc/title → "r/Genealogy"
    parts = url.split("/r/", 1)
    if len(parts) < 2:
        return "reddit"
    name = parts[1].split("/", 1)[0]
    return f"r/{name}" if name else "reddit"


def _published_date(item: dict[str, Any]) -> str:
    raw = item.get("publishedDate") or ""
    return raw[:10] if raw else "unknown"


def discover(
    *,
    exa_key: str,
    anthropic_key: str,
    icps: list[str],
    days: int,
    per_query: int,
    model: str = "haiku",
    dry_run: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Return ``{icp: [{url, title, excerpt, subreddit, posted, reply}, ...]}``."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
    model_id = enrich_personalize.MODEL_IDS.get(model, enrich_personalize.MODEL_IDS["haiku"])
    seen_urls: set[str] = set()
    results: dict[str, list[dict[str, Any]]] = {}

    for icp in icps:
        queries = ICP_QUERIES.get(icp)
        if not queries:
            log(f"  unknown icp '{icp}', skipping")
            continue

        log(f"\n== reddit search [{icp}] ({len(queries)} queries, since {cutoff}) ==")
        bucket: list[dict[str, Any]] = []
        for q in queries:
            try:
                hits = _exa_search_reddit(
                    api_key=exa_key, query=q, start_date=cutoff, num_results=per_query
                )
            except Exception as e:  # noqa: BLE001
                log(f"  exa error on {q!r}: {e}")
                continue
            log(f"  + [{len(hits)}]  {q[:60]}")

            for h in hits:
                url = h.get("url") or ""
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                title = (h.get("title") or "").strip()
                excerpt = " ".join((h.get("text") or "").split()).strip()[:600]
                if not title or not excerpt:
                    continue

                if dry_run:
                    reply = "(dry-run: reply not generated)"
                else:
                    try:
                        reply = _draft_reply(
                            api_key=anthropic_key,
                            model_id=model_id,
                            subreddit=_subreddit_of(url),
                            title=title,
                            excerpt=excerpt,
                        )
                    except Exception as e:  # noqa: BLE001
                        log(f"  claude error on {url}: {e}")
                        continue

                bucket.append(
                    {
                        "url": url,
                        "title": title,
                        "excerpt": excerpt,
                        "subreddit": _subreddit_of(url),
                        "posted": _published_date(h),
                        "reply": reply,
                        "query": q,
                    }
                )
        results[icp] = bucket
        log(f"  = {len(bucket)} unique candidates for {icp}")

    return results


def render_markdown(results: dict[str, list[dict[str, Any]]], *, days: int) -> str:
    today = today_iso()
    total = sum(len(v) for v in results.values())
    lines: list[str] = [
        f"# Reddit question queue — {today}",
        "",
        f"{total} candidate questions across {len(results)} ICPs, posted in the last {days} days.",
        "",
        "**Before posting:** Read the OP carefully, edit the suggested reply to fit your voice and",
        "the conversation, and post manually from a real account with prior comment history. If you",
        "post from an account affiliated with Lost Rabbit Digital, add an affiliation disclosure.",
        "Do not post the same reply across multiple subreddits.",
        "",
    ]
    for icp, items in results.items():
        lines.append(f"## ICP: {icp}  ({len(items)} candidates)")
        lines.append("")
        if not items:
            lines.append("_No candidates this run._")
            lines.append("")
            continue
        for it in items:
            lines.extend(
                [
                    f"### [{it['subreddit']}] {it['title']}",
                    "",
                    f"- **URL:** {it['url']}",
                    f"- **Posted:** {it['posted']}",
                    f"- **Matched query:** {it['query']}",
                    "",
                    f"**Excerpt:** {it['excerpt']}",
                    "",
                    "**Suggested reply:**",
                    "",
                ]
            )
            for line in it["reply"].splitlines() or [""]:
                lines.append(f"> {line}" if line.strip() else ">")
            lines.append("")
            lines.append("---")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.find_reddit_questions")
    p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p.add_argument("--per-query", type=int, default=DEFAULT_PER_QUERY)
    p.add_argument(
        "--icp",
        default=",".join(ICP_QUERIES.keys()),
        help=f"comma-separated ICPs. available: {','.join(ICP_QUERIES.keys())}",
    )
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--model", default="haiku", choices=["haiku", "sonnet", "opus"])
    p.add_argument("--dry-run", action="store_true", help="skip reply generation")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(list(argv) if argv is not None else sys.argv[1:])

    exa_key = os.environ.get("EXA_API_KEY", "")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not exa_key:
        log("error: EXA_API_KEY not set")
        return 1
    if not anthropic_key and not args.dry_run:
        log("error: ANTHROPIC_API_KEY not set (use --dry-run to skip reply drafting)")
        return 1

    icps = [s.strip() for s in args.icp.split(",") if s.strip()]
    results = discover(
        exa_key=exa_key,
        anthropic_key=anthropic_key,
        icps=icps,
        days=args.days,
        per_query=args.per_query,
        model=args.model,
        dry_run=args.dry_run,
    )

    out_path = args.out or (DEFAULT_OUT_DIR / f"{today_iso()}.md")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_markdown(results, days=args.days))

    total = sum(len(v) for v in results.values())
    log(f"\nwrote {total} candidates to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
