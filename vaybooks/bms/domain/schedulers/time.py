"""Business-timezone helpers for scheduler due checks.

Schedules are authored and evaluated in the business timezone (Asia/Kolkata)
while timestamps stay naive UTC to match the repository convention used by the
rest of the codebase.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

BUSINESS_TIMEZONE_NAME = "Asia/Kolkata"

# IST has no daylight saving, so a fixed offset is exact. ZoneInfo is preferred
# when the platform ships tz data, but Windows installs frequently do not.
_FIXED_IST = timezone(timedelta(hours=5, minutes=30))


def _business_tz():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(BUSINESS_TIMEZONE_NAME)
    except Exception:
        return _FIXED_IST


IST = _business_tz()


def utc_now() -> datetime:
    """Naive UTC now, matching the storage convention."""
    return datetime.utcnow()


def as_utc_naive(value: Optional[datetime]) -> Optional[datetime]:
    """Normalise any datetime to naive UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def to_business(value: Optional[datetime]) -> Optional[datetime]:
    """Convert a naive-UTC (or aware) timestamp to an aware business-time value."""
    if value is None:
        return None
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware.astimezone(IST)


def from_business(value: Optional[datetime]) -> Optional[datetime]:
    """Convert an aware business-time value back to naive UTC for storage."""
    if value is None:
        return None
    aware = value.replace(tzinfo=IST) if value.tzinfo is None else value
    return aware.astimezone(timezone.utc).replace(tzinfo=None)


def business_now() -> datetime:
    return to_business(utc_now())


def business_today() -> date:
    return business_now().date()


def business_datetime(day: date, at: time) -> datetime:
    """Aware business-time datetime for a calendar day and wall-clock time."""
    return datetime.combine(day, at).replace(tzinfo=IST)


def business_day_bounds(day: Optional[date] = None) -> tuple[datetime, datetime]:
    """Naive-UTC [start, end) bounds of a business calendar day."""
    target = day or business_today()
    start = business_datetime(target, time(0, 0))
    end = start + timedelta(days=1)
    return from_business(start), from_business(end)


def business_date_of(value: Optional[datetime]) -> Optional[date]:
    converted = to_business(value)
    return converted.date() if converted else None


def format_business(value: Optional[datetime], fmt: str = "%d %b %Y %I:%M %p") -> str:
    converted = to_business(value)
    return converted.strftime(fmt) if converted else "—"
