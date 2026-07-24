"""Map boutique TimeEntry records to FullCalendar event dicts."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional

from vaybooks.bms.domain.boutique.time_tracking.entities import TaskType, TimeEntry

TYPE_COLORS = {
    TaskType.ETD: "#1f6feb",
    TaskType.DELIVERY: "#1a7f37",
    TaskType.ACTIVITY: "#9a6700",
}

TYPE_LABELS = {
    TaskType.ETD: "ETD",
    TaskType.DELIVERY: "Delivery",
    TaskType.ACTIVITY: "Activity",
}

ACTIVITY_PALETTE = [
    "#9a6700",
    "#8250df",
    "#bf3989",
    "#0969da",
    "#1a7f37",
    "#bc4c00",
    "#57606a",
]


def activity_color(activity_name: str) -> str:
    if not activity_name:
        return TYPE_COLORS[TaskType.ACTIVITY]
    idx = abs(hash(activity_name)) % len(ACTIVITY_PALETTE)
    return ACTIVITY_PALETTE[idx]


def entry_color(entry: TimeEntry) -> str:
    if entry.task_type == TaskType.ACTIVITY:
        return activity_color(entry.activity_name)
    return TYPE_COLORS.get(entry.task_type, "#57606a")


def _normalize_hhmm(value: str) -> Optional[str]:
    text = (value or "").strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return f"{hour:02d}:{minute:02d}"


def _event_title(entry: TimeEntry) -> str:
    label = entry.activity_name or TYPE_LABELS.get(entry.task_type, "Task")
    parts = [label, entry.order_number]
    if entry.bill_number:
        parts.append(entry.bill_number)
    return " · ".join(p for p in parts if p)


def _is_overnight(start_hhmm: str, end_hhmm: str) -> bool:
    return end_hhmm < start_hhmm


def entry_to_calendar_event(entry: TimeEntry) -> dict:
    """Convert one TimeEntry into a FullCalendar event dict."""
    color = entry_color(entry)
    title = _event_title(entry)
    base = {
        "id": entry.id,
        "title": title,
        "backgroundColor": color,
        "borderColor": color,
        "extendedProps": {
            "entry_id": entry.id,
            "task_type": entry.task_type.value,
            "order_number": entry.order_number,
            "bill_number": entry.bill_number,
            "activity_name": entry.activity_name,
            "worker_name": entry.worker_name,
            "notes": entry.notes,
            "work_date": entry.work_date.isoformat(),
            "start_time": entry.start_time,
            "end_time": entry.end_time,
            "duration_minutes": entry.duration_minutes,
        },
    }

    is_milestone = entry.task_type in (TaskType.ETD, TaskType.DELIVERY)
    start_hhmm = _normalize_hhmm(entry.start_time)
    end_hhmm = _normalize_hhmm(entry.end_time)

    if is_milestone or not start_hhmm or not end_hhmm:
        return {
            **base,
            "start": entry.work_date.isoformat(),
            "allDay": True,
        }

    start_dt = datetime.combine(
        entry.work_date, datetime.strptime(start_hhmm, "%H:%M").time()
    )
    end_date = entry.work_date
    if _is_overnight(start_hhmm, end_hhmm):
        end_date = entry.work_date + timedelta(days=1)
    end_dt = datetime.combine(
        end_date, datetime.strptime(end_hhmm, "%H:%M").time()
    )
    return {
        **base,
        "start": start_dt.isoformat(timespec="seconds"),
        "end": end_dt.isoformat(timespec="seconds"),
        "allDay": False,
    }


def entries_to_calendar_events(entries: Iterable[TimeEntry]) -> List[dict]:
    return [entry_to_calendar_event(e) for e in entries]


def visible_range_around(anchor: date | None = None) -> tuple[date, date]:
    """Padded range so month/week/day navigation still has loaded events."""
    anchor = anchor or date.today()
    start = (anchor.replace(day=1) - timedelta(days=1)).replace(day=1)
    # End: last day of month two months after anchor's month
    year = anchor.year
    month = anchor.month + 2
    while month > 12:
        month -= 12
        year += 1
    # day before first of month+3
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    return start, end
