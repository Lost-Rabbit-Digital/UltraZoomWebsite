"""Stage 5 (optional): poll Imgur for view/upvote counts on posted items.

Each invocation snapshots all rows in ``posts`` newer than ``--max-age-days``
and writes a fresh row to ``analytics``. Per-day cron is fine — Imgur's
view counter updates lazily anyway.

Run:
    python analytics.py --verbose
    python analytics.py --max-age-days 30 --csv-out latest.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import connect, init_db
from imgur import ImgurError, fetch_gallery_stats


def _record(conn, *, post_id: int, data: dict) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO analytics (
            post_id, sampled_at, views, ups, downs, points, comment_count, in_gallery
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            post_id, now,
            data.get("views"), data.get("ups"), data.get("downs"),
            data.get("points"), data.get("comment_count"),
            1 if data.get("in_gallery") else 0,
        ),
    )


def _dump_csv(conn, out_path: Path) -> None:
    rows = conn.execute(
        """
        SELECT p.imgur_id, p.gallery_url, p.title_used, p.tags_used, p.posted_at,
               c.source, c.source_url,
               a.sampled_at, a.views, a.ups, a.downs, a.points, a.comment_count, a.in_gallery
        FROM posts p
        JOIN candidates c ON c.id = p.candidate_id
        LEFT JOIN analytics a ON a.id = (
            SELECT id FROM analytics WHERE post_id = p.id
            ORDER BY sampled_at DESC LIMIT 1
        )
        ORDER BY p.posted_at DESC
        """,
    ).fetchall()
    with out_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "imgur_id", "gallery_url", "title", "tags", "posted_at",
            "source", "source_url",
            "sampled_at", "views", "ups", "downs", "points", "comments", "in_gallery",
        ])
        for r in rows:
            w.writerow(list(r))
    print(f"Wrote {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 5: poll Imgur stats.")
    p.add_argument("--max-age-days", type=int, default=60,
                   help="Skip posts older than this (Imgur stats stop moving)")
    p.add_argument("--csv-out", type=Path, default=None,
                   help="If set, also dump latest stats to a CSV")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    init_db()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.max_age_days)).isoformat()
    sampled = 0
    failed = 0
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, imgur_id FROM posts WHERE posted_at >= ? ORDER BY posted_at DESC",
            (cutoff,),
        ).fetchall()
        for row in rows:
            try:
                data = fetch_gallery_stats(row["imgur_id"])
            except ImgurError as e:
                failed += 1
                print(f"[analytics] {row['imgur_id']}: {e}", file=sys.stderr)
                continue
            _record(conn, post_id=row["id"], data=data)
            sampled += 1
            if args.verbose:
                print(f"[analytics] {row['imgur_id']} views={data.get('views')} "
                      f"ups={data.get('ups')} comments={data.get('comment_count')}")
        conn.commit()
        if args.csv_out:
            _dump_csv(conn, args.csv_out)
    print(f"Sampled {sampled} / failed {failed}")


if __name__ == "__main__":
    main()
