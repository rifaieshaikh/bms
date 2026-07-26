"""Map CRM activities to FullCalendar event dicts."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Iterable

from vaybooks.bms.domain.crm.enums import ActivityStatus
from vaybooks.bms.ui.crm_adapters import field, record_id, text

STATUS_COLORS: dict[str, str] = {
    ActivityStatus.SCHEDULED.value: "#0969da",
    ActivityStatus.IN_PROGRESS.value: "#8250df",
    ActivityStatus.COMPLETED.value: "#1a7f37",
    ActivityStatus.CANCELLED.value: "#57606a",
    ActivityStatus.MISSED.value: "#cf222e",
    ActivityStatus.REVERSED.value: "#57606a",
}

OVERDUE_COLOR = "#cf222e"
HIGH_PRIORITY_COLOR = "#bc4c00"
TODAY_COLOR = "#0a7f83"
DEFAULT_COLOR = "#57606a"
DEFAULT_DURATION_MINUTES = 30

OPEN_STATUSES = (ActivityStatus.SCHEDULED.value, ActivityStatus.IN_PROGRESS.value)


def activity_color(activity: Any, *, now: datetime | None = None) -> str:
    status = text(field(activity, "status"))
    start = field(activity, "scheduled_at", "activity_at")
    reference = now or datetime.now()
    if (
        status in OPEN_STATUSES
        and isinstance(start, datetime)
        and start < reference
    ):
        return OVERDUE_COLOR
    if status in OPEN_STATUSES and text(field(activity, "priority")) in {
        "High",
        "Urgent",
    }:
        return HIGH_PRIORITY_COLOR
    if (
        status in OPEN_STATUSES
        and isinstance(start, (datetime, date))
        and (start.date() if isinstance(start, datetime) else start)
        == reference.date()
    ):
        return TODAY_COLOR
    return STATUS_COLORS.get(status, DEFAULT_COLOR)


def event_title(activity: Any) -> str:
    parts = [
        text(field(activity, "activity_type"), default="Activity"),
        text(field(activity, "party_name")),
    ]
    return " · ".join(p for p in parts if p)


def activity_to_event(activity: Any, *, now: datetime | None = None) -> dict | None:
    """Convert one CRM activity into a FullCalendar event dict.

    Returns ``None`` when the activity has no usable date, so it is simply
    omitted from the calendar instead of breaking the render.
    """
    start = field(activity, "scheduled_at", "activity_at")
    if not isinstance(start, (datetime, date)):
        return None

    color = activity_color(activity, now=now)
    event: dict[str, Any] = {
        "id": record_id(activity),
        "title": event_title(activity),
        "backgroundColor": color,
        "borderColor": color,
        "extendedProps": {
            "activity_id": record_id(activity),
            "activity_type": text(field(activity, "activity_type")),
            "status": text(field(activity, "status")),
            "priority": text(field(activity, "priority")),
            "party_name": text(field(activity, "party_name")),
            "assigned_user_name": text(field(activity, "assigned_user_name")),
            "origin": text(field(activity, "origin")),
            "lead_id": text(field(activity, "lead_id")),
            "enquiry_id": text(field(activity, "enquiry_id")),
            "customer_id": text(field(activity, "customer_id")),
        },
    }

    if not isinstance(start, datetime):
        event["start"] = start.isoformat()
        event["allDay"] = True
        return event

    # Activities are points in time; give them a nominal slot so the
    # week and day views can lay them out.
    event["start"] = start.isoformat(timespec="seconds")
    event["end"] = (
        start + timedelta(minutes=DEFAULT_DURATION_MINUTES)
    ).isoformat(timespec="seconds")
    event["allDay"] = False
    return event


def activities_to_events(
    activities: Iterable[Any], *, now: datetime | None = None
) -> list[dict]:
    events = (activity_to_event(a, now=now) for a in activities or [])
    return [event for event in events if event is not None]
