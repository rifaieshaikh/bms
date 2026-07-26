"""Plain-language recurring schedules for scheduler jobs and reports.

Operators pick a frequency and a time of day; cron is derived internally and is
never shown in the UI. Due checks use calendar arithmetic in the business
timezone so "Every N days" behaves correctly, which cron cannot express.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional

from vaybooks.bms.domain.schedulers.time import (
    business_datetime,
    from_business,
    to_business,
    utc_now,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError

FREQ_DAILY = "daily"
FREQ_WEEKDAYS = "weekdays"
FREQ_WEEKLY = "weekly"
FREQ_EVERY_N_DAYS = "every_n_days"

FREQUENCIES: tuple[str, ...] = (
    FREQ_DAILY,
    FREQ_WEEKDAYS,
    FREQ_WEEKLY,
    FREQ_EVERY_N_DAYS,
)

FREQUENCY_LABELS: dict[str, str] = {
    FREQ_DAILY: "Daily",
    FREQ_WEEKDAYS: "Weekdays (Mon-Fri)",
    FREQ_WEEKLY: "Weekly",
    FREQ_EVERY_N_DAYS: "Every N days",
}

WEEKDAY_LABELS: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)

# Guard against pathological scans when a schedule can never fire.
_MAX_DAY_SCAN = 400


@dataclass
class ScheduleSpec:
    frequency: str = FREQ_DAILY
    time_of_day: str = "06:00"
    weekday: int = 0
    interval_days: int = 1

    @property
    def at(self) -> time:
        return parse_time_of_day(self.time_of_day)


def parse_time_of_day(value: str) -> time:
    parts = (value or "").strip().split(":")
    if len(parts) != 2:
        raise ValidationError(f"Invalid time of day: {value!r} (expected HH:MM)")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValidationError(f"Invalid time of day: {value!r}") from exc
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValidationError(f"Time of day out of range: {value!r}")
    return time(hour=hour, minute=minute)


def validate_schedule(spec: ScheduleSpec) -> None:
    if spec.frequency not in FREQUENCIES:
        raise ValidationError(f"Unknown schedule frequency: {spec.frequency!r}")
    parse_time_of_day(spec.time_of_day)
    if spec.frequency == FREQ_WEEKLY and not 0 <= int(spec.weekday) <= 6:
        raise ValidationError("Weekly schedules need a weekday between Monday and Sunday")
    if spec.frequency == FREQ_EVERY_N_DAYS and int(spec.interval_days) < 1:
        raise ValidationError("Every N days needs an interval of at least 1 day")


def _format_clock(at: time) -> str:
    return at.strftime("%I:%M %p").lstrip("0")


def format_schedule(spec: ScheduleSpec) -> str:
    """Human summary such as 'Weekdays at 9:00 AM'."""
    try:
        at = parse_time_of_day(spec.time_of_day)
    except ValidationError:
        return "Invalid schedule"
    clock = _format_clock(at)
    if spec.frequency == FREQ_DAILY:
        return f"Every day at {clock}"
    if spec.frequency == FREQ_WEEKDAYS:
        return f"Weekdays at {clock}"
    if spec.frequency == FREQ_WEEKLY:
        index = int(spec.weekday) % 7
        return f"Every {WEEKDAY_LABELS[index]} at {clock}"
    if spec.frequency == FREQ_EVERY_N_DAYS:
        every = max(1, int(spec.interval_days))
        if every == 1:
            return f"Every day at {clock}"
        return f"Every {every} days at {clock}"
    return "Invalid schedule"


def schedule_to_cron(spec: ScheduleSpec) -> str:
    """Five-field cron used for storage and diagnostics only.

    Every N days cannot be represented faithfully by cron; the derived
    expression is an approximation and due checks never rely on it.
    """
    at = parse_time_of_day(spec.time_of_day)
    if spec.frequency == FREQ_DAILY:
        return f"{at.minute} {at.hour} * * *"
    if spec.frequency == FREQ_WEEKDAYS:
        return f"{at.minute} {at.hour} * * 1-5"
    if spec.frequency == FREQ_WEEKLY:
        # cron weekdays are Sunday-based; ScheduleSpec.weekday is Monday-based.
        cron_dow = (int(spec.weekday) + 1) % 7
        return f"{at.minute} {at.hour} * * {cron_dow}"
    every = max(1, int(spec.interval_days))
    return f"{at.minute} {at.hour} */{every} * *"


def _fires_on(day: date, spec: ScheduleSpec) -> bool:
    if spec.frequency == FREQ_DAILY:
        return True
    if spec.frequency == FREQ_WEEKDAYS:
        return day.weekday() < 5
    if spec.frequency == FREQ_WEEKLY:
        return day.weekday() == int(spec.weekday) % 7
    return True


def _interval_anchor(spec: ScheduleSpec, last_run_at: Optional[datetime]) -> Optional[date]:
    last_business = to_business(last_run_at)
    return last_business.date() if last_business else None


def previous_fire(
    spec: ScheduleSpec,
    *,
    last_run_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """Most recent scheduled instant at or before ``now`` (naive UTC)."""
    validate_schedule(spec)
    reference = to_business(now or utc_now())
    at = parse_time_of_day(spec.time_of_day)

    if spec.frequency == FREQ_EVERY_N_DAYS:
        anchor = _interval_anchor(spec, last_run_at)
        if anchor is None:
            candidate = business_datetime(reference.date(), at)
            if candidate > reference:
                candidate = business_datetime(reference.date() - timedelta(days=1), at)
            return from_business(candidate)
        every = max(1, int(spec.interval_days))
        candidate_day = anchor + timedelta(days=every)
        candidate = business_datetime(candidate_day, at)
        if candidate > reference:
            return None
        # Walk forward to the latest due instant that has already passed.
        while True:
            nxt = business_datetime(candidate_day + timedelta(days=every), at)
            if nxt > reference:
                break
            candidate_day = candidate_day + timedelta(days=every)
            candidate = nxt
        return from_business(candidate)

    day = reference.date()
    for _ in range(_MAX_DAY_SCAN):
        if _fires_on(day, spec):
            candidate = business_datetime(day, at)
            if candidate <= reference:
                return from_business(candidate)
        day -= timedelta(days=1)
    return None


def next_run_at(
    spec: ScheduleSpec,
    *,
    last_run_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> Optional[datetime]:
    """Next scheduled instant strictly after ``now`` (naive UTC)."""
    validate_schedule(spec)
    reference = to_business(now or utc_now())
    at = parse_time_of_day(spec.time_of_day)

    if spec.frequency == FREQ_EVERY_N_DAYS:
        every = max(1, int(spec.interval_days))
        anchor = _interval_anchor(spec, last_run_at)
        if anchor is None:
            candidate = business_datetime(reference.date(), at)
            if candidate <= reference:
                candidate = business_datetime(reference.date() + timedelta(days=1), at)
            return from_business(candidate)
        candidate_day = anchor + timedelta(days=every)
        for _ in range(_MAX_DAY_SCAN):
            candidate = business_datetime(candidate_day, at)
            if candidate > reference:
                return from_business(candidate)
            candidate_day += timedelta(days=every)
        return None

    day = reference.date()
    for _ in range(_MAX_DAY_SCAN):
        if _fires_on(day, spec):
            candidate = business_datetime(day, at)
            if candidate > reference:
                return from_business(candidate)
        day += timedelta(days=1)
    return None


def is_job_due(
    spec: ScheduleSpec,
    *,
    last_run_at: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> bool:
    """True when a scheduled instant has passed and no run covered it yet."""
    previous = previous_fire(spec, last_run_at=last_run_at, now=now)
    if previous is None:
        return False
    if last_run_at is None:
        return True
    return last_run_at < previous
