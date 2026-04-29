"""Ultra Zoom outreach pipeline (manual Apollo CSV → Sheets).

Reads an Apollo people-export CSV from ``outreach/inbox/<campaign>/``,
drafts a personalized Touch 1 and Touch 2 for every verified-email row
via Claude, and appends the results to two tabs of the campaign's
Google Sheet — one per touch — that MailMeteor imports independently.

Usage:

    # Realtors campaign (boden@lostrabbitdigital.com sender)
    python -m outreach.run_ultrazoom --campaign realtors

    # Smoke-test against a sample CSV without spending API credit
    python -m outreach.run_ultrazoom --campaign realtors --dry-run

    # Pin to a specific CSV (otherwise the latest by mtime in the
    # campaign's inbox folder is used)
    python -m outreach.run_ultrazoom --campaign realtors \\
        --inbox-csv outreach/inbox/ultrazoom-realtors/2026-04-29.csv

Required env vars (live runs):
    ANTHROPIC_API_KEY                  personalization
    GOOGLE_SHEET_ID_UZ_REALTORS       Sheets target for the Realtors campaign
    Google Sheets auth via ADC / Workload Identity Federation in CI

Email verification is intentionally not in this pipeline. Apollo's saved
search already filters to ``Email Status = Verified``; layering a
secondary verifier (Hunter / NeverBounce / ZeroBounce) on top costs API
credits without changing reply rates in practice. The ingest step
re-asserts the Verified-only filter as defense in depth.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import ingest_apollo_csv, stage_sheet
from .campaign_config import CAMPAIGNS, CampaignConfig, by_name
from .config import DEFAULT_MODEL, INBOX_DIR, Config, ensure_dirs
from .enrich_personalize import personalize as claude_personalize
from .util import log, now_iso, today_iso


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _campaign_choices() -> list[str]:
    return sorted({c.name for c in CAMPAIGNS.values()} | {"realtors"})


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="outreach.run_ultrazoom")
    p.add_argument(
        "--campaign",
        required=True,
        choices=_campaign_choices(),
        help="Which Ultra Zoom campaign to run.",
    )
    p.add_argument(
        "--inbox-csv",
        type=Path,
        default=None,
        help="Path to a specific Apollo CSV. Defaults to the newest "
        "*.csv in outreach/inbox/<campaign>/.",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--model", default=DEFAULT_MODEL, choices=["haiku", "sonnet", "opus"])
    p.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Cap the number of leads processed from the CSV. 0 = no cap.",
    )
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Pipeline steps
# ---------------------------------------------------------------------------


def _resolve_inbox_csv(campaign: CampaignConfig, override: Path | None) -> Path:
    if override is not None:
        return override
    folder = INBOX_DIR / campaign.name
    found = ingest_apollo_csv.latest_csv_in(folder)
    if found is None:
        raise FileNotFoundError(
            f"no Apollo CSV in {folder}. Drop a *.csv there or pass "
            "--inbox-csv."
        )
    return found


def _week_number(ref: datetime | None = None) -> int:
    """ISO week-of-year. Used in the ``utm_campaign`` value so each
    week's send batch is attributable.
    """
    return (ref or datetime.now(timezone.utc)).isocalendar().week


def _force_re_prefix(subject: str) -> str:
    """Ensure a T2 subject starts with ``Re: `` so Gmail threads it
    under the T1 conversation.
    """
    s = subject.strip()
    if s.lower().startswith("re:"):
        return s
    return f"Re: {s}"


def _process_lead(
    lead: dict[str, Any],
    *,
    cfg: Config,
    campaign: CampaignConfig,
    model: str,
    week: int,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str]:
    """Run T1 + T2 personalization for one lead.

    Returns ``(t1_row, t2_row, "")`` on success or
    ``(None, None, drop_reason)``. Apollo's verified-only filter is
    trusted — no secondary email verification step.
    """
    if cfg.dry_run:
        t1 = {
            "subject": "[dry-run T1 subject]",
            "body": "[dry-run T1 body — not actually generated.]",
        }
        t2 = {
            "subject": "Re: [dry-run T1 subject]",
            "body": "[dry-run T2 body — not actually generated.]",
        }
    else:
        t1, err1 = claude_personalize(
            lead,
            campaign=campaign,
            touch=1,
            api_key=cfg.anthropic_key or "",
            model=model,
        )
        if t1 is None:
            return None, None, f"t1_personalization: {err1}"
        t2, err2 = claude_personalize(
            lead,
            campaign=campaign,
            touch=2,
            api_key=cfg.anthropic_key or "",
            model=model,
        )
        if t2 is None:
            return None, None, f"t2_personalization: {err2}"

    # Force T2 subject to thread under T1 in Gmail. Gmail threads when
    # the normalized subjects match (Re:/Fwd: stripped), so the easiest
    # way to guarantee threading is to use Touch 1's subject verbatim
    # with a Re: prefix.
    t2["subject"] = _force_re_prefix(t1["subject"])

    enriched_at = now_iso()

    landing_t1 = campaign.render_landing_link(week=week, touch=1)
    landing_t2 = campaign.render_landing_link(week=week, touch=2)

    t1_row = dict(lead)
    t1_row["personalized_subject"] = t1["subject"]
    # Substitute ``{{landing_page_link}}`` at stage time. The AI is told
    # to leave the literal merge tag in the body for validation; the
    # runner resolves it before the row hits the Sheet so MailMeteor
    # ships a real URL.
    t1_row["personalized_body"] = t1["body"].replace(
        "{{landing_page_link}}", landing_t1
    )
    t1_row["enriched_at"] = enriched_at
    t1_row["notes"] = f"{campaign.name} | t1 | sender={campaign.sender_email}"

    t2_row = dict(lead)
    t2_row["personalized_subject"] = t2["subject"]
    t2_row["personalized_body"] = t2["body"].replace(
        "{{landing_page_link}}", landing_t2
    )
    t2_row["enriched_at"] = enriched_at
    t2_row["notes"] = f"{campaign.name} | t2 | sender={campaign.sender_email}"

    return t1_row, t2_row, ""


def _check_keys(cfg: Config) -> list[str]:
    if cfg.dry_run:
        return []
    missing: list[str] = []
    if not cfg.anthropic_key:
        missing.append("ANTHROPIC_API_KEY")
    if not cfg.sheet_id:
        missing.append("(campaign-specific Sheet ID env var)")
    return missing


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    ensure_dirs()

    campaign = by_name(args.campaign)
    cfg = Config.from_env(sheet_id_env=campaign.sheet_id_env, dry_run=args.dry_run)

    missing = _check_keys(cfg)
    if missing:
        log("error: missing env vars:")
        for n in missing:
            log(f"  - {n}")
        return 1

    log(
        f"== UZ outreach @ {today_iso()}  campaign={campaign.name}  "
        f"sender={campaign.sender_email}  dry_run={args.dry_run} =="
    )

    # 1. Load CSV.
    csv_path = _resolve_inbox_csv(campaign, args.inbox_csv)
    log(f"  csv: {csv_path}")
    candidates = ingest_apollo_csv.load_csv(
        csv_path, source=f"apollo-csv-{campaign.name}"
    )
    if not candidates:
        log("no verified candidates in CSV. nothing to do.")
        return 0
    if args.limit and len(candidates) > args.limit:
        log(f"  limit: trimming {len(candidates)} → {args.limit}")
        candidates = candidates[: args.limit]

    # 2. Dedupe against existing T1 + T2 tabs in this campaign's Sheet.
    seen: set[str] = set()
    if not cfg.dry_run:
        try:
            seen |= stage_sheet.existing_emails_in(
                cfg, tab=campaign.sheet_tab_t1, columns=campaign.sheet_columns_t1
            )
            seen |= stage_sheet.existing_emails_in(
                cfg, tab=campaign.sheet_tab_t2, columns=campaign.sheet_columns_t2
            )
        except Exception as e:  # noqa: BLE001
            log(
                f"  warning: could not read existing sheet emails ({e}). "
                "proceeding without sheet-side dedupe."
            )
    candidates, dropped_dupes = ingest_apollo_csv.dedupe_by_email(
        candidates, against=seen
    )
    log(
        f"  after dedupe: {len(candidates)} new candidates "
        f"({dropped_dupes} duplicates dropped)"
    )

    # 3. Personalize each lead's T1 + T2.
    week = _week_number()
    t1_rows: list[dict[str, Any]] = []
    t2_rows: list[dict[str, Any]] = []
    drops: dict[str, int] = {}
    for i, lead in enumerate(candidates, start=1):
        log(
            f"  [{i}/{len(candidates)}] {lead.get('editor_email')} "
            f"({lead.get('domain')})"
        )
        t1_row, t2_row, drop = _process_lead(
            lead,
            cfg=cfg,
            campaign=campaign,
            model=args.model,
            week=week,
        )
        if drop:
            log(f"    dropped: {drop}")
            drops[drop] = drops.get(drop, 0) + 1
            continue
        assert t1_row is not None and t2_row is not None
        t1_rows.append(t1_row)
        t2_rows.append(t2_row)

    log(
        f"\npersonalization done. t1={len(t1_rows)} t2={len(t2_rows)} "
        f"drops={drops}"
    )

    # 4. Stage to the two tabs.
    appended_t1 = stage_sheet.stage(
        cfg,
        t1_rows,
        tab=campaign.sheet_tab_t1,
        columns=campaign.sheet_columns_t1,
        dry_run=cfg.dry_run,
    )
    appended_t2 = stage_sheet.stage(
        cfg,
        t2_rows,
        tab=campaign.sheet_tab_t2,
        columns=campaign.sheet_columns_t2,
        dry_run=cfg.dry_run,
    )

    log(
        f"\n=== UZ run complete. campaign={campaign.name} "
        f"appended_t1={appended_t1} appended_t2={appended_t2} ==="
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
