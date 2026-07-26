"""Schedule maths: formatting, cron mapping, due checks, next-run."""

from datetime import date, datetime, time, timedelta

import pytest

from vaybooks.bms.domain.schedulers.schedule import (
    FREQ_DAILY,
    FREQ_EVERY_N_DAYS,
    FREQ_WEEKDAYS,
    FREQ_WEEKLY,
    ScheduleSpec,
    format_schedule,
    is_job_due,
    next_run_at,
    parse_time_of_day,
    previous_fire,
    schedule_to_cron,
    validate_schedule,
)
from vaybooks.bms.domain.schedulers.time import (
    business_datetime,
    business_today,
    from_business,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError


def _utc(spec_date: date, hour: int, minute: int = 0) -> datetime:
    """A business-local wall clock converted to the naive UTC we store."""
    return from_business(business_datetime(spec_date, time(hour, minute)))


def test_parse_time_of_day_accepts_hh_mm():
    assert parse_time_of_day("06:00") == time(6, 0)
    assert parse_time_of_day("23:45") == time(23, 45)


@pytest.mark.parametrize("bad", ["", "24:00", "6", "06:60", "abc"])
def test_parse_time_of_day_rejects_bad_values(bad):
    with pytest.raises(ValidationError):
        parse_time_of_day(bad)


def test_format_schedule_is_plain_language():
    assert format_schedule(ScheduleSpec(FREQ_DAILY, "06:00")) == "Every day at 6:00 AM"
    assert format_schedule(ScheduleSpec(FREQ_WEEKDAYS, "09:30")) == "Weekdays at 9:30 AM"
    assert (
        format_schedule(ScheduleSpec(FREQ_WEEKLY, "18:00", weekday=0))
        == "Every Monday at 6:00 PM"
    )
    assert (
        format_schedule(ScheduleSpec(FREQ_EVERY_N_DAYS, "06:00", interval_days=3))
        == "Every 3 days at 6:00 AM"
    )
    assert (
        format_schedule(ScheduleSpec(FREQ_EVERY_N_DAYS, "06:00", interval_days=1))
        == "Every day at 6:00 AM"
    )


def test_schedule_to_cron_matches_frequency():
    assert schedule_to_cron(ScheduleSpec(FREQ_DAILY, "06:00")) == "0 6 * * *"
    assert schedule_to_cron(ScheduleSpec(FREQ_WEEKDAYS, "06:30")) == "30 6 * * 1-5"
    assert schedule_to_cron(ScheduleSpec(FREQ_WEEKLY, "06:00", weekday=6)) == "0 6 * * 0"
    # "Every N days" has no faithful cron form; the daily form is a marker only.
    assert (
        schedule_to_cron(ScheduleSpec(FREQ_EVERY_N_DAYS, "06:00", interval_days=5))
        == "0 6 */5 * *"
    )


def test_validate_schedule_rejects_bad_input():
    with pytest.raises(ValidationError):
        validate_schedule(ScheduleSpec("hourly", "06:00"))
    with pytest.raises(ValidationError):
        validate_schedule(ScheduleSpec(FREQ_WEEKLY, "06:00", weekday=9))
    with pytest.raises(ValidationError):
        validate_schedule(ScheduleSpec(FREQ_EVERY_N_DAYS, "06:00", interval_days=0))


def test_daily_job_is_due_after_the_hour_and_not_twice_a_day():
    spec = ScheduleSpec(FREQ_DAILY, "06:00")
    today = business_today()
    yesterday = today - timedelta(days=1)
    ran_yesterday = _utc(yesterday, 6, 5)

    # Before today's fire time, yesterday's run still covers the schedule.
    assert is_job_due(spec, last_run_at=ran_yesterday, now=_utc(today, 5, 30)) is False
    assert is_job_due(spec, last_run_at=ran_yesterday, now=_utc(today, 6, 30)) is True
    # Once it has run past the fire time, the same day must not fire again.
    assert is_job_due(spec, last_run_at=_utc(today, 6, 5), now=_utc(today, 6, 30)) is False


def test_a_job_that_never_ran_is_due_for_the_missed_occurrence():
    spec = ScheduleSpec(FREQ_DAILY, "06:00")
    assert is_job_due(spec, last_run_at=None, now=_utc(business_today(), 5, 30)) is True


def test_weekly_job_only_fires_on_its_weekday():
    spec = ScheduleSpec(FREQ_WEEKLY, "06:00", weekday=0)
    monday = date(2026, 7, 20)
    tuesday = date(2026, 7, 21)
    assert is_job_due(spec, last_run_at=None, now=_utc(monday, 7, 0)) is True
    # Tuesday still fires because Monday's occurrence was never executed.
    assert is_job_due(spec, last_run_at=None, now=_utc(tuesday, 7, 0)) is True
    assert (
        is_job_due(spec, last_run_at=_utc(monday, 6, 1), now=_utc(tuesday, 7, 0))
        is False
    )


def test_weekdays_schedule_skips_the_weekend():
    spec = ScheduleSpec(FREQ_WEEKDAYS, "06:00")
    saturday = date(2026, 7, 25)
    friday = date(2026, 7, 24)
    assert previous_fire(spec, now=_utc(saturday, 7, 0)).date() == friday


def test_every_n_days_uses_the_last_run_as_the_anchor():
    spec = ScheduleSpec(FREQ_EVERY_N_DAYS, "06:00", interval_days=3)
    anchor = _utc(date(2026, 7, 20), 6, 5)
    assert is_job_due(spec, last_run_at=anchor, now=_utc(date(2026, 7, 22), 7, 0)) is False
    assert is_job_due(spec, last_run_at=anchor, now=_utc(date(2026, 7, 23), 7, 0)) is True


def test_next_run_at_is_in_the_future():
    spec = ScheduleSpec(FREQ_DAILY, "06:00")
    now = _utc(business_today(), 7, 0)
    nxt = next_run_at(spec, last_run_at=None, now=now)
    assert nxt is not None and nxt > now
