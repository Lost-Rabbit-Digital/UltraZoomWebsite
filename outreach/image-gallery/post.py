"""Stage 4: drain the queue.

Run via cron every ``POST_INTERVAL_HOURS``; on each invocation we claim
at most one queue row whose ``scheduled_at <= now``, upload it to Imgur,
submit to the public gallery, and record the post.

A simple "claim → post → record" loop keeps things idempotent: if a run
crashes after upload but before recording, the next run notices the row
is still claimed and either retries the gallery step or fails out for
human attention (``--max-attempts`` controls how many tries).

Run:
    python post.py --verbose
    python post.py --dry-run         # picks a row, uploads nothing, prints plan
    python post.py --max-attempts 3
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import ENHANCED_DIR, POSTED_DIR, ensure_dirs
from db import connect, init_db
from imgur import ImgurError, submit_to_gallery, upload_image


def _claim_one(conn, *, max_attempts: int):
    """Return (queue_row, candidate_row) or None."""
    now = datetime.now(timezone.utc).isoformat()
    row = conn.execute(
        """
        SELECT q.*, c.* FROM queue q
        JOIN candidates c ON c.id = q.candidate_id
        WHERE q.status IN ('pending', 'claimed')
          AND q.scheduled_at <= ?
          AND q.attempts < ?
        ORDER BY q.scheduled_at ASC
        LIMIT 1
        """,
        (now, max_attempts),
    ).fetchone()
    if not row:
        return None
    conn.execute(
        "UPDATE queue SET status='claimed', claimed_at=?, attempts=attempts+1 WHERE id=?",
        (now, row["id"]),
    )
    conn.commit()
    return row


def _record_post(conn, *, queue_id: int, candidate_id: int,
                 image_id: str, deletehash: str | None,
                 link: str | None, gallery_url: str,
                 title: str, tags: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO posts (
            candidate_id, queue_id, posted_at,
            imgur_id, imgur_deletehash, imgur_url, gallery_url,
            title_used, tags_used
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (candidate_id, queue_id, now, image_id, deletehash, link,
         gallery_url, title, tags),
    )
    conn.execute("UPDATE queue SET status='posted' WHERE id=?", (queue_id,))
    conn.execute("UPDATE candidates SET status='posted' WHERE id=?", (candidate_id,))
    conn.commit()


def _record_failure(conn, *, queue_id: int, err: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE queue SET status='pending', last_error=?, claimed_at=? WHERE id=?",
        (err[:1000], now, queue_id),
    )
    conn.commit()


def _archive(enhanced_path: Path, image_hash: str) -> Path:
    """Copy the file we just shipped into posted/ for forensic reference."""
    out = POSTED_DIR / image_hash[:2] / f"{image_hash}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        shutil.copy2(enhanced_path, out)
    return out


def _resolve_path(rel: str) -> Path:
    """Stored paths are relative to outreach/."""
    return Path(__file__).parent.parent / rel


def post_one(*, dry_run: bool, verbose: bool, max_attempts: int) -> bool:
    init_db()
    ensure_dirs()
    with connect() as conn:
        row = _claim_one(conn, max_attempts=max_attempts)
        if not row:
            if verbose:
                print("[post] no rows due")
            return False

        candidate_id = row["candidate_id"]
        queue_id = row["id"]
        title = row["title"] or row["source_title"] or "Untitled"
        tags = row["tags"] or ""
        enhanced = _resolve_path(row["enhanced_path"])

        if not enhanced.exists():
            err = f"enhanced file missing on disk: {enhanced}"
            print(f"[post] cand={candidate_id} {err}", file=sys.stderr)
            _record_failure(conn, queue_id=queue_id, err=err)
            return False

        if dry_run:
            print(
                f"[dry-run] would upload {enhanced.name} ({enhanced.stat().st_size}B) "
                f"as title={title!r} tags={tags!r}"
            )
            # Release the claim so we don't tax retry counts on dry runs.
            conn.execute(
                "UPDATE queue SET status='pending', attempts=attempts-1 WHERE id=?",
                (queue_id,),
            )
            return True

        try:
            up = upload_image(enhanced, title=title)
            if not up.image_id:
                raise ImgurError("upload returned no image id")
            description = _description_for(row)
            gal = submit_to_gallery(
                up.image_id,
                title=title,
                tags=[t.strip() for t in tags.split(",") if t.strip()],
                mature=False,
            )
        except ImgurError as e:
            print(f"[post] cand={candidate_id} ImgurError: {e}", file=sys.stderr)
            _record_failure(conn, queue_id=queue_id, err=str(e))
            return False
        except Exception as e:
            print(f"[post] cand={candidate_id} unexpected: {e}", file=sys.stderr)
            _record_failure(conn, queue_id=queue_id, err=str(e))
            return False

        _record_post(
            conn,
            queue_id=queue_id, candidate_id=candidate_id,
            image_id=up.image_id, deletehash=up.deletehash,
            link=up.link, gallery_url=gal.gallery_url,
            title=title, tags=tags,
        )
        _archive(enhanced, row["image_hash"])
        if verbose or True:  # always log on real posts
            print(f"[post] cand={candidate_id} → {gal.gallery_url}")
        return True


def _description_for(row) -> str:
    """Description shown beneath the gallery post.

    Stays short and credits the source.  Imgur description max is 1024.
    """
    bits = []
    if row["source"] == "reddit" and row["source_url"]:
        bits.append(f"Source: {row['source_url']}")
    elif row["source"] == "commons" and row["source_url"]:
        bits.append(f"Source: Wikimedia Commons — {row['source_url']}")
    elif row["source"] == "nasa" and row["source_url"]:
        bits.append(f"Source: NASA APOD — {row['source_url']}")
    if row["source_author"]:
        bits.append(f"Credit: {row['source_author']}")
    bits.append("Enhanced with Ultra Zoom (https://ultrazoom.app).")
    return "\n".join(bits)[:1024]


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 4: post the next due queue item to Imgur.")
    p.add_argument("--dry-run", action="store_true",
                   help="Don't upload; print what we'd do and release the claim.")
    p.add_argument("--max-attempts", type=int, default=3,
                   help="Skip queue rows that have already failed this many times.")
    p.add_argument("--all-due", action="store_true",
                   help="Drain every due row this invocation (default: one per run).")
    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    posted = 0
    while True:
        ok = post_one(dry_run=args.dry_run, verbose=args.verbose,
                      max_attempts=args.max_attempts)
        if ok:
            posted += 1
        if not args.all_due or not ok:
            break
    if args.verbose:
        print(f"[post] done, posted={posted}")


if __name__ == "__main__":
    main()
