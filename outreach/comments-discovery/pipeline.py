"""Orchestrates the full pipeline:

  1. Run Exa queries -> URL candidates
  2. Fetch each URL, extract metadata + comment system + zoom signal
  3. Filter: must have open comments and a non-zero relevance score
  4. For survivors, call Claude to draft a suggested comment
  5. Insert everything into SQLite for human review

Run with:
    EXA_API_KEY=... ANTHROPIC_API_KEY=... python pipeline.py [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable

import anthropic

from db import connect, init_db
from exa_search import DEFAULT_ALLOWLIST, QUERIES, search
from fetcher import fetch
from suggest import suggest_comment

MIN_SCORE = 0.3
SLEEP_BETWEEN_FETCHES = 1.5  # be a polite citizen


def already_seen(conn, url: str) -> bool:
    row = conn.execute("SELECT 1 FROM candidates WHERE url = ?", (url,)).fetchone()
    return row is not None


def insert_candidate(conn, fr, suggestion=None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO candidates (
            url, site_title, article_title, published_at, fetched_at,
            comments_open, comment_system, last_comment_at, comment_count,
            header_image_url, header_image_caption, image_count, word_count,
            excerpt, zoom_signal, relevance_score,
            suggested_comment, suggestion_model, suggestion_cost_usd,
            status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            fr.url, fr.site_title, fr.article_title, fr.published_at, now,
            int(fr.comments_open), fr.comment_system, fr.last_comment_at, fr.comment_count,
            fr.header_image_url, fr.header_image_caption, fr.image_count, fr.word_count,
            fr.excerpt, fr.zoom_signal, fr.relevance_score,
            suggestion.text if suggestion else None,
            suggestion.model if suggestion else None,
            suggestion.cost_usd if suggestion else None,
            "new",
        ),
    )


def run(queries: Iterable[str], limit: int, dry_run: bool, verbose: bool) -> None:
    init_db()

    raw_candidates = []
    for q in queries:
        if verbose:
            print(f"[exa] {q}", file=sys.stderr)
        try:
            results = search(q, num_results=limit, include_domains=DEFAULT_ALLOWLIST,
                             start_published_date="2024-01-01")
        except Exception as e:
            print(f"[exa] error on '{q}': {e}", file=sys.stderr)
            continue
        raw_candidates.extend(results)

    # Dedupe by URL
    seen = set()
    unique = []
    for c in raw_candidates:
        if c.url and c.url not in seen:
            seen.add(c.url)
            unique.append(c)

    if verbose:
        print(f"[exa] {len(unique)} unique candidates", file=sys.stderr)

    client = anthropic.Anthropic() if not dry_run else None
    total_cost = 0.0
    inserted = 0
    skipped_seen = 0
    skipped_score = 0
    skipped_closed = 0
    skipped_suggest = 0

    with connect() as conn:
        for ec in unique:
            if already_seen(conn, ec.url):
                skipped_seen += 1
                continue

            fr = fetch(ec.url)
            time.sleep(SLEEP_BETWEEN_FETCHES)

            if fr.error:
                if verbose:
                    print(f"[fetch] {ec.url} -> error: {fr.error}", file=sys.stderr)
                continue

            if not fr.comments_open:
                skipped_closed += 1
                if verbose:
                    print(f"[fetch] {ec.url} -> comments closed", file=sys.stderr)
                continue

            if fr.relevance_score < MIN_SCORE:
                skipped_score += 1
                if verbose:
                    print(f"[fetch] {ec.url} -> score {fr.relevance_score} below {MIN_SCORE}", file=sys.stderr)
                continue

            suggestion = None
            if not dry_run:
                try:
                    suggestion = suggest_comment(
                        article_title=fr.article_title or "",
                        excerpt=fr.excerpt,
                        header_caption=fr.header_image_caption,
                        zoom_signal=fr.zoom_signal,
                        client=client,
                    )
                    total_cost += suggestion.cost_usd
                    if suggestion.skip:
                        skipped_suggest += 1
                        if verbose:
                            print(f"[suggest] {ec.url} -> SKIP", file=sys.stderr)
                        # Still insert it as a candidate so the human can see it was considered
                except Exception as e:
                    print(f"[suggest] error on {ec.url}: {e}", file=sys.stderr)

            insert_candidate(conn, fr, suggestion)
            inserted += 1
            if verbose:
                print(f"[insert] {fr.relevance_score} {ec.url}", file=sys.stderr)

    print(f"""
Pipeline run complete.
  unique candidates  : {len(unique)}
  already in DB      : {skipped_seen}
  comments closed    : {skipped_closed}
  below score {MIN_SCORE}  : {skipped_score}
  AI said SKIP       : {skipped_suggest}
  inserted           : {inserted}
  Claude API cost    : ${total_cost:.4f}
""".strip())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true",
                   help="Don't call Claude API, just discover and insert with empty suggestions")
    p.add_argument("--limit", type=int, default=15,
                   help="Max results per Exa query")
    p.add_argument("--query", action="append",
                   help="Override default queries (can pass multiple times)")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    queries = args.query if args.query else QUERIES
    run(queries, limit=args.limit, dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    main()
