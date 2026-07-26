from datetime import datetime, timedelta
from types import SimpleNamespace

from vaybooks.bms.ui.components.crm.whatsapp import build_reminder_draft
from vaybooks.bms.ui.pages.crm.calendar.events import (
    HIGH_PRIORITY_COLOR,
    OVERDUE_COLOR,
    activity_color,
    activity_to_event,
)
from vaybooks.bms.ui.pages.crm.export import records_to_csv


def test_calendar_highlights_overdue_and_high_priority_work():
    now = datetime(2026, 7, 25, 12)
    overdue = SimpleNamespace(
        status="Scheduled",
        scheduled_at=now - timedelta(days=1),
        priority="Medium",
    )
    urgent = SimpleNamespace(
        status="Scheduled",
        scheduled_at=now + timedelta(days=1),
        priority="Urgent",
    )
    assert activity_color(overdue, now=now) == OVERDUE_COLOR
    assert activity_color(urgent, now=now) == HIGH_PRIORITY_COLOR


def test_calendar_event_keeps_related_record_context():
    activity = SimpleNamespace(
        id="activity-1",
        activity_type="Called",
        party_name="Acme",
        status="Scheduled",
        priority="High",
        scheduled_at=datetime(2026, 7, 25, 10),
        lead_id="lead-1",
        enquiry_id="",
        customer_id="customer-1",
        assigned_user_name="Rep",
        origin="Manual",
        due_at=None,
    )
    event = activity_to_event(activity, now=datetime(2026, 7, 24))
    assert event["id"] == "activity-1"
    assert event["extendedProps"]["customer_id"] == "customer-1"
    assert event["extendedProps"]["lead_id"] == "lead-1"


def test_whatsapp_draft_uses_encoded_click_to_chat_url():
    draft = build_reminder_draft(
        customer_id="customer-1",
        customer_name="Acme",
        phone="9876543210",
        outstanding_amount=1250,
        business_name="VayBooks",
    )
    assert draft.whatsapp_url.startswith("https://wa.me/919876543210?text=")
    assert "Acme" in draft.message
    assert "1,250.00" in draft.message


def test_lead_export_handles_empty_and_populated_rows():
    columns = (("name", "Lead"), ("status", "Status"))
    assert records_to_csv([], columns).decode("utf-8-sig") == "Lead,Status\n"
    csv_text = records_to_csv(
        [SimpleNamespace(name="Acme", status="New")], columns
    ).decode("utf-8-sig")
    assert "Acme,New" in csv_text
