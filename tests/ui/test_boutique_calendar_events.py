from datetime import date

from vaybooks.bms.domain.boutique.time_tracking.entities import TaskType, TimeEntry
from vaybooks.bms.ui.pages.boutique.calendar.events import (
    entry_to_calendar_event,
    visible_range_around,
)


def _activity(**kwargs) -> TimeEntry:
    defaults = dict(
        order_id="o1",
        order_number="O-1",
        bill_id="b1",
        bill_number="ZB001",
        activity_id="act-stitch",
        activity_name="Stitching",
        work_date=date(2026, 8, 10),
        start_time="09:00",
        end_time="11:30",
        duration_minutes=150,
        worker_name="Asha",
        task_type=TaskType.ACTIVITY,
        id="entry-act-1",
    )
    defaults.update(kwargs)
    return TimeEntry(**defaults)


def test_activity_maps_to_timed_event():
    event = entry_to_calendar_event(_activity())
    assert event["allDay"] is False
    assert event["start"] == "2026-08-10T09:00:00"
    assert event["end"] == "2026-08-10T11:30:00"
    assert "Stitching" in event["title"]
    assert event["id"] == "entry-act-1"
    assert event["extendedProps"]["worker_name"] == "Asha"


def test_overnight_activity_ends_next_day():
    event = entry_to_calendar_event(
        _activity(start_time="22:00", end_time="02:00", duration_minutes=240)
    )
    assert event["allDay"] is False
    assert event["start"] == "2026-08-10T22:00:00"
    assert event["end"] == "2026-08-11T02:00:00"


def test_etd_and_delivery_are_all_day():
    etd = entry_to_calendar_event(
        _activity(
            id="etd-1",
            activity_id="system:etd",
            activity_name="ETD",
            start_time="",
            end_time="",
            duration_minutes=0,
            task_type=TaskType.ETD,
            work_date=date(2026, 8, 15),
        )
    )
    assert etd["allDay"] is True
    assert etd["start"] == "2026-08-15"
    assert "end" not in etd or etd.get("end") in (None, "")

    delivery = entry_to_calendar_event(
        _activity(
            id="del-1",
            activity_id="delivery:d1",
            activity_name="Delivery",
            start_time="",
            end_time="",
            duration_minutes=0,
            task_type=TaskType.DELIVERY,
            work_date=date(2026, 8, 20),
        )
    )
    assert delivery["allDay"] is True
    assert delivery["start"] == "2026-08-20"


def test_activity_missing_times_falls_back_to_all_day():
    event = entry_to_calendar_event(
        _activity(start_time="", end_time="", duration_minutes=0)
    )
    assert event["allDay"] is True
    assert event["start"] == "2026-08-10"


def test_visible_range_around_pads_months():
    start, end = visible_range_around(date(2026, 8, 15))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 10, 31)
