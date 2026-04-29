"""Environment loading, paths, and tunable thresholds.

All API keys come from env vars; nothing is hardcoded. The CLI surfaces a
``--dry-run`` flag that bypasses key requirements so smoke tests work
without any secrets configured.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Repo-relative paths. ``OUTREACH_DIR`` resolves to the directory containing
# this file, so the pipeline works whether invoked from the repo root or
# elsewhere.
OUTREACH_DIR = Path(__file__).resolve().parent
INBOX_DIR = OUTREACH_DIR / "inbox"
CACHE_DIR = OUTREACH_DIR / "cache"
PROMPTS_DIR = OUTREACH_DIR / "prompts"
CAMPAIGNS_DIR = OUTREACH_DIR / "campaigns"

EXCLUDED_DOMAINS_PATH = OUTREACH_DIR / "excluded_domains.txt"
SUPPRESSION_PATH = OUTREACH_DIR / "suppression.csv"

VERIFY_CACHE = CACHE_DIR / "verify_cache.json"
VERIFY_TTL_DAYS = 60

# Validation thresholds shared by all campaigns. Per-campaign overrides
# (banned words, required tokens, max word count) live on the
# ``CampaignConfig`` object in ``campaign_config.py``.
PERSONALIZATION_BODY_MIN_WORDS = 50
PERSONALIZATION_BODY_MAX_WORDS = 180
PERSONALIZATION_SUBJECT_MAX_WORDS = 9

# Default Claude model for personalization. Haiku is fast and cheap and
# easily strong enough for an opener-quality draft. Override on the CLI
# with ``--model sonnet`` for higher-stakes batches.
DEFAULT_MODEL = "haiku"

# Sheet columns the pipeline owns on each per-touch tab. MailMeteor adds
# its own columns (Merge status, Date sent, Opens, Clicks, etc.) to the
# right of these and we never touch those.
#
# ``personalized_subject`` and ``personalized_body`` are what MailMeteor
# pulls into the Subject and Body fields of its template. The other
# columns are merge tags the AI is allowed to reference (e.g.
# ``{{first_name}}`` inside the body) plus reference fields for
# debugging. Per-campaign extras (``specific_recent_topic`` for press)
# are appended to this base in ``campaign_config.py``.
BASE_SHEET_COLUMNS = [
    "discovered_at",
    "source",
    "first_name",
    "last_name",
    "editor_email",
    "editor_title",
    "company",
    "domain",
    "linkedin_url",
    "city",
    "state",
    "industry",
    "keywords",
    "apollo_contact_id",
    "personalized_subject",
    "personalized_body",
    "status",
    "enriched_at",
    "notes",
]


@dataclass
class Config:
    """Resolved runtime configuration. Constructed once per CLI invocation."""

    anthropic_key: str | None = None
    hunter_key: str | None = None
    neverbounce_key: str | None = None
    zerobounce_key: str | None = None
    sheet_id: str | None = None
    dry_run: bool = False

    @classmethod
    def from_env(cls, *, sheet_id_env: str, dry_run: bool = False) -> "Config":
        return cls(
            anthropic_key=os.environ.get("ANTHROPIC_API_KEY"),
            hunter_key=os.environ.get("HUNTER_API_KEY"),
            neverbounce_key=os.environ.get("NEVERBOUNCE_API_KEY"),
            zerobounce_key=os.environ.get("ZEROBOUNCE_API_KEY"),
            sheet_id=os.environ.get(sheet_id_env),
            dry_run=dry_run,
        )

    def has_verifier(self) -> bool:
        return any([self.hunter_key, self.neverbounce_key, self.zerobounce_key])


def ensure_dirs() -> None:
    for d in (CACHE_DIR, PROMPTS_DIR, INBOX_DIR):
        d.mkdir(parents=True, exist_ok=True)
