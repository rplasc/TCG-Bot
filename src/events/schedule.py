"""Deterministic event scheduler.

Given the current time, returns the active daily and weekly events by indexing
into the registry — no DB state is needed to know what's active. Rotation happens
at ``ROTATION_HOUR`` America/Los_Angeles, matching the daily shop rotation.
"""

import zoneinfo
from datetime import datetime, timedelta

from src.events.config import DAILY_EVENTS, WEEKLY_EVENTS, EventDef

_TZ = zoneinfo.ZoneInfo("America/Los_Angeles")
ROTATION_HOUR = 8  # 8 AM PST, aligned with the shop rotation


def _now(now: datetime | None) -> datetime:
    return now or datetime.now(_TZ)


def _effective_date(now: datetime):
    """The rotation day: before ROTATION_HOUR we still belong to the previous day."""
    if now.hour < ROTATION_HOUR:
        return now.date() - timedelta(days=1)
    return now.date()


def daily_index(now: datetime | None = None) -> int:
    return _effective_date(_now(now)).toordinal()


def week_index(now: datetime | None = None) -> int:
    return _effective_date(_now(now)).toordinal() // 7


def active_daily(now: datetime | None = None) -> EventDef | None:
    if not DAILY_EVENTS:
        return None
    return DAILY_EVENTS[daily_index(now) % len(DAILY_EVENTS)]


def active_weekly(now: datetime | None = None) -> EventDef | None:
    if not WEEKLY_EVENTS:
        return None
    return WEEKLY_EVENTS[week_index(now) % len(WEEKLY_EVENTS)]


def period_key(now: datetime | None = None) -> str:
    """Stable key for the current daily+weekly combo; changes when either rotates."""
    now = _now(now)
    d = active_daily(now)
    w = active_weekly(now)
    return f"{daily_index(now)}:{d.id if d else '-'}|{week_index(now)}:{w.id if w else '-'}"
