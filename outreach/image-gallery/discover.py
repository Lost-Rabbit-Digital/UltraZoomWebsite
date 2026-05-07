"""Stage 1 orchestrator.

Pulls candidates from configured sources, downloads each image, dedupes
by sha256, and inserts rows into ``candidates`` with status='new'.

Run:
    python discover.py --reddit --commons --nasa --verbose
    python discover.py --reddit --subreddit spaceporn --subreddit pics
    python discover.py --exa --query "rare deep-sea creature photographs"

Idempotent on (source, source_id) and on image_hash, so re-running won't
double-insert.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import mimetypes
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Iterable

import requests
from PIL import Image, UnidentifiedImageError

from config import (
    CANDIDATES_DIR,
    DEFAULT_SUBREDDITS,
    REDDIT_MIN_SCORE,
    REDDIT_TOP_WINDOW,
    USER_AGENT,
    ensure_dirs,
)
from db import connect, init_db
from sources import commons as commons_source
from sources import exa as exa_source
from sources import reddit as reddit_source
from sources.base import Candidate

DOWNLOAD_TIMEOUT = 30
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50MB cap before Stage 2 resizes


def _hash_image_path(image_hash: str, ext: str) -> Path:
    """Sharded path: candidates/ab/abcdef…ext (avoids huge flat dirs)."""
    return CANDIDATES_DIR / image_hash[:2] / f"{image_hash}{ext}"


def _ext_for(content_type: str | None, url: str) -> str:
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed if guessed != ".jpe" else ".jpg"
    # Fall back to URL extension
    for cand in (".jpg", ".jpeg", ".png", ".webp"):
        if url.lower().split("?")[0].endswith(cand):
            return ".jpg" if cand == ".jpeg" else cand
    return ".jpg"


def _download(url: str) -> tuple[bytes, str | None] | None:
    try:
        with requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=DOWNLOAD_TIMEOUT,
            stream=True,
        ) as r:
            r.raise_for_status()
            total = 0
            chunks: list[bytes] = []
            for chunk in r.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                chunks.append(chunk)
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    print(f"[download] {url} exceeded {MAX_DOWNLOAD_BYTES} bytes, skipping")
                    return None
            return b"".join(chunks), r.headers.get("Content-Type")
    except requests.RequestException as e:
        print(f"[download] {url}: {e}")
        return None


def _dimensions(data: bytes) -> tuple[int | None, int | None, str | None]:
    try:
        with Image.open(BytesIO(data)) as im:
            im.verify()
        with Image.open(BytesIO(data)) as im:
            return im.size[0], im.size[1], (im.format or "").lower()
    except (UnidentifiedImageError, OSError):
        return None, None, None


def _already_seen(conn, source: str, source_id: str, image_hash: str) -> bool:
    if conn.execute(
        "SELECT 1 FROM candidates WHERE source=? AND source_id=?",
        (source, source_id),
    ).fetchone():
        return True
    if conn.execute(
        "SELECT 1 FROM candidates WHERE image_hash=?",
        (image_hash,),
    ).fetchone():
        return True
    return False


def _insert(conn, c: Candidate, *, image_path: Path, image_hash: str,
            image_bytes: int, w: int | None, h: int | None, mime: str | None) -> None:
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """
        INSERT INTO candidates (
            source, source_id, source_url, source_title, source_author,
            source_score, source_published_at, source_metadata,
            image_url, image_path, image_hash, image_width, image_height,
            image_bytes, image_mime, fetched_at, title, status
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            c.source, c.source_id, c.source_url, c.title, c.author,
            c.score, c.published_at, json.dumps(c.metadata or {}),
            c.image_url, str(image_path.relative_to(CANDIDATES_DIR.parent)),
            image_hash, w, h, image_bytes, mime, now, c.title, "new",
        ),
    )


def ingest(candidates: Iterable[Candidate], *, verbose: bool) -> dict[str, int]:
    stats = {"considered": 0, "duplicate": 0, "broken": 0, "inserted": 0}
    with connect() as conn:
        for c in candidates:
            stats["considered"] += 1
            dl = _download(c.image_url)
            if not dl:
                stats["broken"] += 1
                continue
            data, content_type = dl
            digest = hashlib.sha256(data).hexdigest()
            if _already_seen(conn, c.source, c.source_id, digest):
                stats["duplicate"] += 1
                if verbose:
                    print(f"[skip] dup {c.source}/{c.source_id}")
                continue
            w, h, fmt = _dimensions(data)
            if not w or not h:
                stats["broken"] += 1
                if verbose:
                    print(f"[skip] not-an-image {c.source}/{c.source_id}")
                continue
            ext = _ext_for(content_type, c.image_url)
            path = _hash_image_path(digest, ext)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            # Sidecar JSON for forensic dump (helpful if DB gets blown away)
            path.with_suffix(path.suffix + ".json").write_text(
                json.dumps(dataclasses.asdict(c), indent=2)
            )
            _insert(
                conn, c,
                image_path=path,
                image_hash=digest,
                image_bytes=len(data),
                w=w, h=h,
                mime=fmt or (content_type or "").split(";")[0].strip() or None,
            )
            stats["inserted"] += 1
            if verbose:
                print(f"[ok] {c.source}/{c.source_id} {w}x{h} {len(data)}B")
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description="Stage 1: discover candidate images.")
    p.add_argument("--reddit", action="store_true")
    p.add_argument("--commons", action="store_true",
                   help="Wikimedia Commons Picture of the Day (recent)")
    p.add_argument("--nasa", action="store_true", help="NASA APOD recent")
    p.add_argument("--exa", action="store_true", help="Exa.ai semantic search")
    p.add_argument("--all", action="store_true", help="Enable every source")

    p.add_argument("--subreddit", action="append",
                   help="Subreddit name (repeatable). Default: see config.")
    p.add_argument("--min-score", type=int, default=REDDIT_MIN_SCORE)
    p.add_argument("--reddit-window", default=REDDIT_TOP_WINDOW,
                   choices=["hour", "day", "week", "month", "year", "all"])
    p.add_argument("--limit-per-sub", type=int, default=25)

    p.add_argument("--commons-days", type=int, default=7,
                   help="How many days of POTD to walk back")
    p.add_argument("--nasa-days", type=int, default=7,
                   help="How many days of APOD to walk back")

    p.add_argument("--query", action="append",
                   help="Exa query (repeatable). Required if --exa is set.")
    p.add_argument("--exa-limit", type=int, default=5)

    p.add_argument("--verbose", action="store_true")
    args = p.parse_args()

    enabled = {
        "reddit":  args.reddit  or args.all,
        "commons": args.commons or args.all,
        "nasa":    args.nasa    or args.all,
        "exa":     args.exa     or args.all,
    }
    if not any(enabled.values()):
        print("No source enabled. Pass --reddit / --commons / --nasa / --exa or --all.")
        sys.exit(2)
    if enabled["exa"] and not args.query:
        print("--exa requires at least one --query.")
        sys.exit(2)

    ensure_dirs()
    init_db()

    candidates: list[Candidate] = []
    if enabled["reddit"]:
        subs = args.subreddit or DEFAULT_SUBREDDITS
        if args.verbose:
            print(f"[reddit] subs={subs} min_score={args.min_score} window={args.reddit_window}")
        candidates.extend(reddit_source.discover(
            subs,
            min_score=args.min_score,
            window=args.reddit_window,
            limit_per_sub=args.limit_per_sub,
        ))
    if enabled["commons"] or enabled["nasa"]:
        if args.verbose:
            print(f"[commons/nasa] commons_days={args.commons_days} nasa_days={args.nasa_days}")
        candidates.extend(commons_source.discover(
            commons_potd_days=args.commons_days if enabled["commons"] else 0,
            nasa_lookback_days=args.nasa_days if enabled["nasa"] else 0,
        ))
    if enabled["exa"]:
        if args.verbose:
            print(f"[exa] queries={args.query}")
        candidates.extend(exa_source.discover(args.query, limit_per_query=args.exa_limit))

    if args.verbose:
        print(f"[discover] {len(candidates)} raw candidates")

    stats = ingest(candidates, verbose=args.verbose)
    print(
        f"Discovery complete.\n"
        f"  considered : {stats['considered']}\n"
        f"  inserted   : {stats['inserted']}\n"
        f"  duplicate  : {stats['duplicate']}\n"
        f"  broken     : {stats['broken']}"
    )


if __name__ == "__main__":
    main()
