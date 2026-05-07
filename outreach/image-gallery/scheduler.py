"""Slot scheduler for the queue.

The posting window is configurable in ``config.py`` (default: 10am-12am ET,
every 2h = 8 slots/day). When Stage 3 approves a candidate, we ask the
scheduler for the next free slot and write that ISO-UTC timestamp into
``queue.scheduled_at``. Stage 4's cron job claims rows whose
``scheduled_at <= now``.

Slot collision: never schedule two candidates within ``POST_INTERVAL_HOURS``
of each other, regardless of which day. So if today's last slot fills up,
the next approval lands on tomorrow's first slot.
"""
from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone
from typing import Iterable, Optional
from zoneinfo import ZoneInfo

from config import (
    POST_INTERVAL_HOURS,
    POST_WINDOW_LOCAL_END_HOUR,
    POST_WINDOW_LOCAL_START_HOUR,
    POST_WINDOW_TZ,
)


def _local_slots_for_date(local_date) -> list[datetime]:
    tz = ZoneInfo(POST_WINDOW_TZ)
    out = []
    hour = POST_WINDOW_LOCAL_START_HOUR
    while hour < POST_WINDOW_LOCAL_END_HOUR:
        out.append(datetime.combine(local_date, dt_time(hour=hour), tzinfo=tz))
        hour += POST_INTERVAL_HOURS
    return out


def candidate_slots(*, days_ahead: int = 14, now: Optional[datetime] = None) -> Iterable[datetime]:
    """Yield future slot timestamps (UTC) up to ``days_ahead`` from today."""
    tz = ZoneInfo(POST_WINDOW_TZ)
    now = (now or datetime.now(timezone.utc)).astimezone(tz)
    for offset in range(days_ahead):
        d = (now + timedelta(days=offset)).date()
        for slot_local in _local_slots_for_date(d):
            if slot_local <= now:
                continue
            yield slot_local.astimezone(timezone.utc)


def next_free_slot(taken_iso_utc: Iterable[str], *,
                   now: Optional[datetime] = None,
                   days_ahead: int = 14) -> datetime:
    """Pick the earliest slot that doesn't collide with any in ``taken``.

    ``taken`` is an iterable of ISO-8601 UTC strings (matches what we store
    in ``queue.scheduled_at``).
    """
    taken_dt: list[datetime] = []
    for s in taken_iso_utc:
        if not s:
            continue
        try:
            taken_dt.append(datetime.fromisoformat(s))
        except ValueError:
            continue
    interval = timedelta(hours=POST_INTERVAL_HOURS)
    for slot in candidate_slots(days_ahead=days_ahead, now=now):
        if all(abs((slot - t).total_seconds()) >= interval.total_seconds() - 1
               for t in taken_dt):
            return slot
    raise RuntimeError(
        f"No free posting slot in the next {days_ahead} days "
        f"({len(taken_dt)} already scheduled)"
    )
