"""Environment loading, paths, and tunable thresholds.

All API keys come from env vars; nothing is hardcoded. The CLI surfaces a
``--dry-run`` flag that bypasses key requirements so smoke tests work
without any secrets configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

# Repo-relative paths. ``OUTREACH_DIR`` resolves to the directory containing
# this file, so the pipeline works whether invoked from the repo root or
# elsewhere.
OUTREACH_DIR = Path(__file__).resolve().parent
STATE_DIR = OUTREACH_DIR / "state"
CACHE_DIR = OUTREACH_DIR / "cache"
DROPPED_DIR = OUTREACH_DIR / "dropped"
PROMPTS_DIR = OUTREACH_DIR / "prompts"

SEEN_URLS_PATH = STATE_DIR / "seen_urls.json"
SEEN_DOMAINS_PATH = STATE_DIR / "seen_domains.json"
SEED_ROTATION_PATH = STATE_DIR / "seed_rotation_state.json"

EXCLUDED_DOMAINS_PATH = OUTREACH_DIR / "excluded_domains.txt"
RSS_FEEDS_PATH = OUTREACH_DIR / "rss_feeds.txt"

BRAVE_CACHE = CACHE_DIR / "brave_cache.json"
EXA_CACHE = CACHE_DIR / "exa_cache.json"
HUNTER_CACHE = CACHE_DIR / "hunter_cache.json"
VERIFY_CACHE = CACHE_DIR / "verify_cache.json"

# Default sheet — overridden by GOOGLE_SHEET_ID env var. The fallback value
# is the production target; the override exists for staging copies of the
# sheet during template work.
DEFAULT_SHEET_ID = "1Q-Cr3MdarGttpULJwv6n1eRGoa1GYg7SpB7W5mmYGA0"
SHEET_TAB = "Leads"

# Qualification thresholds. ``MIN_LEAD_SCORE`` is the floor for advancing a
# candidate to enrichment.
MIN_LEAD_SCORE = 50
MAX_AGE_MONTHS = 24
PERSONALIZATION_MAX_WORDS = 25
PERSONALIZATION_HARD_MAX_WORDS = 30

# Cache TTLs.
HUNTER_TTL_DAYS = 90
VERIFY_TTL_DAYS = 60

# Per-run defaults — override on the CLI.
DEFAULT_MAX_STAGE = 15
DEFAULT_PER_QUERY = 15
DEFAULT_MODEL = "haiku"

# Sheet column order. Pipeline owns these; MailMeteor adds its own columns
# (Merge status, Date sent, etc.) to the right and we never touch them.
SHEET_COLUMNS = [
    "discovered_at",
    "source",
    "seed_used",
    "domain",
    "recent_post_url",
    "recent_post_title",
    "recent_post_description",
    "published_date",
    "lead_score",
    "editor_first_name",
    "editor_last_name",
    "editor_email",
    "hunter_confidence",
    "email_status",
    "personalized_opener",
    "status",
    "enriched_at",
    "notes",
]


@dataclass
class Config:
    """Resolved runtime configuration. Constructed once per CLI invocation."""

    brave_key: str | None = None
    exa_key: str | None = None
    hunter_key: str | None = None
    neverbounce_key: str | None = None
    zerobounce_key: str | None = None
    anthropic_key: str | None = None
    google_service_account_json: str | None = None
    sheet_id: str = DEFAULT_SHEET_ID
    serpapi_key: str | None = None
    rss_feed_list_path: Path = field(default_factory=lambda: RSS_FEEDS_PATH)
    dry_run: bool = False

    @classmethod
    def from_env(cls, *, dry_run: bool = False) -> "Config":
        return cls(
            brave_key=os.environ.get("BRAVE_SEARCH_API_KEY"),
            exa_key=os.environ.get("EXA_API_KEY"),
            hunter_key=os.environ.get("HUNTER_API_KEY"),
            neverbounce_key=os.environ.get("NEVERBOUNCE_API_KEY"),
            zerobounce_key=os.environ.get("ZEROBOUNCE_API_KEY"),
            anthropic_key=os.environ.get("ANTHROPIC_API_KEY"),
            google_service_account_json=os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON"),
            sheet_id=os.environ.get("GOOGLE_SHEET_ID", DEFAULT_SHEET_ID),
            serpapi_key=os.environ.get("SERPAPI_KEY"),
            rss_feed_list_path=Path(os.environ.get("RSS_FEED_LIST_PATH", str(RSS_FEEDS_PATH))),
            dry_run=dry_run,
        )

    def require(self, *names: str) -> list[str]:
        """Return any required keys missing from the environment."""
        mapping = {
            "brave": self.brave_key,
            "exa": self.exa_key,
            # Hunter doubles as the default email verifier, so a single
            # Hunter key satisfies both ``hunter`` and ``verify``.
            "hunter": self.hunter_key,
            "verify": self.hunter_key or self.neverbounce_key or self.zerobounce_key,
            "anthropic": self.anthropic_key,
            "google": self.google_service_account_json,
        }
        return [n for n in names if not mapping.get(n)]


def ensure_dirs() -> None:
    for d in (STATE_DIR, CACHE_DIR, DROPPED_DIR, PROMPTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
