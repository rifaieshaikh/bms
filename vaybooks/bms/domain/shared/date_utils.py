from datetime import date, datetime, time, timedelta
from typing import Optional

from vaybooks.bms.domain.shared.exceptions import ValidationError


def parse_time(time_str: str) -> time:
    """Parse HH:MM time string."""
    parts = time_str.strip().split(":")
    if len(parts) != 2:
        raise ValidationError(f"Invalid time format: {time_str}")
    hour, minute = int(parts[0]), int(parts[1])
    return time(hour=hour, minute=minute)


def calculate_duration_minutes(start_time: str, end_time: str) -> int:
    """Calculate duration in minutes from start and end time strings."""
    if not start_time or not end_time:
        raise ValidationError("Start time and end time are required")
    start = parse_time(start_time)
    end = parse_time(end_time)
    start_dt = datetime.combine(date.today(), start)
    end_dt = datetime.combine(date.today(), end)
    if end_dt <= start_dt:
        raise ValidationError("End time must be greater than start time")
    delta = end_dt - start_dt
    return int(delta.total_seconds() / 60)


def minutes_to_hours(minutes: int) -> float:
    return round(minutes / 60, 2)


def is_time_entry_complete(start_time: Optional[str], end_time: Optional[str]) -> bool:
    if not start_time or not end_time:
        return False
    try:
        calculate_duration_minutes(start_time, end_time)
        return True
    except ValidationError:
        return False


def utc_now() -> datetime:
    return datetime.utcnow()


def today() -> date:
    return date.today()
