"""SQLite schema and helpers for the Ultra Zoom outreach pipeline."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path(__file__).parent / "candidates.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    site_title      TEXT,
    article_title   TEXT,
    published_at    TEXT,
    fetched_at      TEXT NOT NULL,

    -- Comment system info
    comments_open       INTEGER NOT NULL DEFAULT 0,
    comment_system      TEXT,             -- disqus, wordpress, facebook, jetpack, unknown
    last_comment_at     TEXT,             -- best-effort
    comment_count       INTEGER,          -- best-effort

    -- Article signal
    header_image_url    TEXT,
    header_image_caption TEXT,
    image_count         INTEGER,
    word_count          INTEGER,
    excerpt             TEXT,             -- first ~500 chars

    -- Why we think it's interesting
    zoom_signal         TEXT,             -- comma-separated keywords matched
    relevance_score     REAL,             -- 0-1, computed locally

    -- AI suggestion
    suggested_comment   TEXT,
    suggestion_model    TEXT,
    suggestion_cost_usd REAL,

    -- Workflow state
    status              TEXT NOT NULL DEFAULT 'new',
                        -- new | reviewed | posted | archived | skipped
    reviewed_at         TEXT,
    posted_at           TEXT,
    notes               TEXT
);

CREATE INDEX IF NOT EXISTS idx_status ON candidates(status);
CREATE INDEX IF NOT EXISTS idx_score  ON candidates(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_fetched ON candidates(fetched_at DESC);
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
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)


if __name__ == "__main__":
    init_db()
    print(f"Initialized {DB_PATH}")
