"""Per-campaign configuration.

Each campaign in this repo (Ultra Zoom Realtors, Ultra Zoom Press) is
described by a ``CampaignConfig`` instance: which inbox folder its
Apollo CSVs land in, which prompt files drive the AI personalization,
which Sheet ID and tabs to write, what merge tags must appear in the
generated body, and what voice/length rules apply.

The HailBytes campaigns live in ``hailbytes-static`` and have their own
copy of this module with their own configs. Keeping per-repo lets each
team own their voice and ICP without cross-repo merge conflicts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    BASE_SHEET_COLUMNS,
    INBOX_DIR,
    PERSONALIZATION_BODY_MAX_WORDS,
    PERSONALIZATION_BODY_MIN_WORDS,
    PROMPTS_DIR,
)


# Words the AI must not use in personalized bodies, regardless of
# campaign. Most of these are sycophancy or vendor-speak that read as
# spam. Per-campaign configs can extend this list.
GLOBAL_BANNED_WORDS = (
    "stumbled",
    "amazing",
    "revolutionize",
    "leverage",
    "synergy",
    "robust solution",
    "cutting-edge",
    "world-class",
    "I love",
    "I loved",
    "great post",
    "great article",
    "really enjoyed",
)


@dataclass(frozen=True)
class CampaignConfig:
    """Everything ``run_ultrazoom.py`` needs to drive one campaign end-to-end."""

    name: str
    """Slug used on CLI (``--campaign realtors``) and in source-of-record
    fields. Lowercase, hyphenated, no spaces."""

    sender_email: str
    """The mailbox MailMeteor will use to send. Stamped on every row in
    ``notes`` so a reader of the Sheet always knows who's sending."""

    sheet_id_env: str
    """Name of the env var holding the Google Sheet ID for this campaign.
    Each campaign has its own Sheet."""

    sheet_tab_t1: str
    """Tab name MailMeteor imports for Touch 1 sends."""

    sheet_tab_t2: str
    """Tab name MailMeteor imports for Touch 2 follow-ups."""

    prompt_t1: Path
    """Markdown file containing the system prompt for Touch 1 drafting."""

    prompt_t2: Path
    """Markdown file containing the system prompt for Touch 2 drafting."""

    extra_columns_t1: tuple[str, ...] = ()
    """Columns appended to ``BASE_SHEET_COLUMNS`` for the T1 tab only.
    Press uses this for ``specific_recent_topic``."""

    extra_columns_t2: tuple[str, ...] = ()
    """Columns appended to ``BASE_SHEET_COLUMNS`` for the T2 tab only."""

    required_tokens_t1: tuple[str, ...] = ()
    """Strings that must appear verbatim in the T1 body (e.g.
    ``"REALTOR30"``, ``"{{landing_page_link}}"``). The validator rejects
    bodies missing any of these."""

    required_tokens_t2: tuple[str, ...] = ()
    """Same idea for T2."""

    extra_banned_words: tuple[str, ...] = ()
    """Per-campaign banned words on top of ``GLOBAL_BANNED_WORDS``."""

    max_body_words: int = PERSONALIZATION_BODY_MAX_WORDS
    """Hard cap on Touch 1 body word count. Enforced by the validator
    after Claude returns a draft; one retry with a stricter prompt
    before the candidate is dropped."""

    min_body_words_t2: int = PERSONALIZATION_BODY_MIN_WORDS
    """Minimum body word count for Touch 2. T2 is a follow-up nudge and
    is typically much shorter than T1, so campaigns can drop this below
    the global ``PERSONALIZATION_BODY_MIN_WORDS`` floor without weakening
    the T1 floor."""

    max_body_words_t2: int = PERSONALIZATION_BODY_MAX_WORDS
    """Hard cap on Touch 2 body word count. Defaults to the same cap as
    T1 but campaigns commonly tighten this since T2 is intentionally
    terse."""

    landing_link_template: str = ""
    """The full ``{{landing_page_link}}`` value the AI is told to embed
    verbatim in T1. UTM placeholders ``{week}`` and ``{touch}`` are
    substituted at render time."""

    coupon_code: str = ""
    """Stripe coupon code the AI is told to embed verbatim in T1 (when
    set). Empty string means no coupon for this campaign (HailBytes
    uses marketplace links rather than Stripe coupons)."""

    persona_summary: str = ""
    """One-paragraph description of the recipient ICP. Goes into the
    cached portion of the system prompt so Claude has consistent
    context for every lead in a batch."""

    voice_summary: str = ""
    """One-paragraph description of the sender voice (e.g. peer-to-peer
    technical for HB ASM, casual professional for UZ Realtors). Cached."""

    sheet_columns_t1: tuple[str, ...] = field(init=False, default=())
    sheet_columns_t2: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        # ``frozen=True`` blocks normal attribute assignment, so use
        # object.__setattr__ to fill the derived columns lists once.
        object.__setattr__(
            self,
            "sheet_columns_t1",
            tuple(BASE_SHEET_COLUMNS) + self.extra_columns_t1,
        )
        object.__setattr__(
            self,
            "sheet_columns_t2",
            tuple(BASE_SHEET_COLUMNS) + self.extra_columns_t2,
        )

    def all_banned_words(self) -> tuple[str, ...]:
        return GLOBAL_BANNED_WORDS + self.extra_banned_words

    def render_landing_link(self, *, week: int, touch: int) -> str:
        return (
            self.landing_link_template.replace("{week}", str(week)).replace(
                "{touch}", str(touch)
            )
        )


REALTORS = CampaignConfig(
    name="ultrazoom-realtors",
    sender_email="boden@lostrabbitdigital.com",
    sheet_id_env="GOOGLE_SHEET_ID_UZ_REALTORS",
    sheet_tab_t1="UZ_Realtors_T1",
    sheet_tab_t2="UZ_Realtors_T2",
    prompt_t1=PROMPTS_DIR / "ultrazoom_realtors_touch1.md",
    prompt_t2=PROMPTS_DIR / "ultrazoom_realtors_touch2.md",
    required_tokens_t1=("{{landing_page_link}}", "REALTOR30"),
    required_tokens_t2=("REALTOR30",),
    # T2 is a 3-paragraph closer, intentionally short. The reference body
    # in ``ultrazoom_realtors_touch2.md`` is ~30 words; cap at 80 to match
    # the touch-2 prompt's "Exceed 80 words total" rule.
    min_body_words_t2=20,
    max_body_words_t2=80,
    landing_link_template=(
        "https://ultrazoom.com/realtors"
        "?utm_source=email&utm_campaign=realtor_w{week}"
        "&utm_content=touch{touch}&coupon=REALTOR30"
    ),
    coupon_code="REALTOR30",
    persona_summary=(
        "U.S. real-estate agents at small (1-50 employee) brokerages who "
        "review hundreds of MLS / Zillow / Redfin listing photos a week and "
        "need to spot defects, staging issues, or fine detail without "
        "downloading every image. Realtor or Real Estate Broker title, "
        "owner / founder / partner / senior / manager seniority. Often "
        "self-employed or small-team; expense decisions are theirs."
    ),
    voice_summary=(
        "Casual but professional. Short sentences. First-person from David, "
        "founder of Ultra Zoom. No vendor-speak, no sycophancy, no "
        "em-dashes (period or comma instead). Reads like a peer reaching "
        "out, not a sales sequence."
    ),
)


CAMPAIGNS: dict[str, CampaignConfig] = {
    REALTORS.name: REALTORS,
    "realtors": REALTORS,  # short alias for the CLI
}


def by_name(name: str) -> CampaignConfig:
    """Resolve a CLI ``--campaign`` value to a config. Raises ``KeyError``
    with a helpful list when the name is unknown.
    """
    try:
        return CAMPAIGNS[name]
    except KeyError as e:
        known = sorted({c.name for c in CAMPAIGNS.values()})
        raise KeyError(
            f"unknown campaign {name!r}. known: {', '.join(known)}"
        ) from e
