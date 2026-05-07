"""SQLite schema for the image-gallery pipeline.

One database, three tables. Candidates start in `candidates`, get an
enhanced row when Stage 2 runs, queue entries when Stage 3 approves them,
post records when Stage 4 ships, and analytics rows when Stage 5 polls.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Source identity
    source          TEXT NOT NULL,        -- reddit | commons | nasa | exa
    source_id       TEXT NOT NULL,        -- e.g. reddit post id, commons file name, nasa date
    source_url      TEXT,                 -- canonical URL on the source site
    source_title    TEXT,                 -- title hint from the source
    source_author   TEXT,                 -- attribution where known
    source_score    INTEGER,              -- e.g. reddit upvotes, NASA has none
    source_published_at TEXT,
    source_metadata TEXT,                 -- JSON blob, opaque to the pipeline

    -- File on disk
    image_url       TEXT NOT NULL,        -- direct image URL we downloaded
    image_path      TEXT,                 -- relative path under candidates/
    image_hash      TEXT UNIQUE,          -- sha256 of the bytes; primary dedup key
    image_width     INTEGER,
    image_height    INTEGER,
    image_bytes     INTEGER,
    image_mime      TEXT,

    fetched_at      TEXT NOT NULL,

    -- Enhancement output (Stage 2)
    enhanced_path   TEXT,
    enhanced_width  INTEGER,
    enhanced_height INTEGER,
    enhanced_bytes  INTEGER,
    enhanced_at     TEXT,
    enhance_error   TEXT,

    -- Human-editable presentation
    title           TEXT,                 -- defaults to source_title; editable in UI
    tags            TEXT,                 -- comma-separated; editable in UI

    -- Workflow state
    status          TEXT NOT NULL DEFAULT 'new',
                    -- new | enhanced | approved | queued | posted | archived | rejected
    reviewed_at     TEXT,
    notes           TEXT,

    UNIQUE(source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_cand_status  ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_cand_source  ON candidates(source);
CREATE INDEX IF NOT EXISTS idx_cand_fetched ON candidates(fetched_at DESC);


CREATE TABLE IF NOT EXISTS queue (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL UNIQUE REFERENCES candidates(id) ON DELETE CASCADE,
    scheduled_at    TEXT NOT NULL,        -- ISO 8601 UTC; Stage 4 polls scheduled_at <= now
    enqueued_at     TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
                    -- pending | claimed | posted | failed
    claimed_at      TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    last_error      TEXT
);

CREATE INDEX IF NOT EXISTS idx_queue_due    ON queue(status, scheduled_at);


CREATE TABLE IF NOT EXISTS posts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id    INTEGER NOT NULL REFERENCES candidates(id),
    queue_id        INTEGER REFERENCES queue(id),
    posted_at       TEXT NOT NULL,

    -- Imgur response
    imgur_id        TEXT NOT NULL,
    imgur_deletehash TEXT,
    imgur_url       TEXT,
    gallery_url     TEXT,
    title_used      TEXT,
    tags_used       TEXT
);

CREATE INDEX IF NOT EXISTS idx_posts_imgur  ON posts(imgur_id);


CREATE TABLE IF NOT EXISTS analytics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id         INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    sampled_at      TEXT NOT NULL,
    views           INTEGER,
    ups             INTEGER,
    downs           INTEGER,
    points          INTEGER,
    comment_count   INTEGER,
    in_gallery      INTEGER                -- 1 if still listed in public gallery
);

CREATE INDEX IF NOT EXISTS idx_analytics_post ON analytics(post_id, sampled_at DESC);
"""


@contextmanager
def connect(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
