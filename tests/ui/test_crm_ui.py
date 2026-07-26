"""CRM UI unit tests: schemas, calendar events, WhatsApp drafts, empty states."""

from datetime import date, datetime, timedelta

import pytest

from vaybooks.bms.domain.crm.entities import CrmActivity, CrmEnquiry, CrmLead
from vaybooks.bms.domain.crm.enums import (
    ActivityStatus,
    CRM_REPORT_DEFINITIONS,
    EnquiryStatus,
    LeadStatus,
)
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.crm.whatsapp import build_reminder_draft
from vaybooks.bms.ui.crm_adapters import CrmAdapter, CrmUnavailable
from vaybooks.bms.ui.crm_list_schemas import (
    CRM_ACTIVITIES,
    CRM_ENQUIRIES,
    CRM_LEADS,
    CRM_REPORT_FILTERS,
    SCHEMAS,
)
from vaybooks.bms.ui.pages.crm.calendar.events import (
    DEFAULT_DURATION_MINUTES,
    OVERDUE_COLOR,
    STATUS_COLORS,
    activities_to_events,
    activity_to_event,
)
from vaybooks.bms.ui.pages.crm.export import (
    ACTIVITY_EXPORT_COLUMNS,
    LEAD_EXPORT_COLUMNS,
    records_to_csv,
    rows_to_csv,
)

TODAY = date.today()
NOW = datetime(2026, 5, 12, 10, 0)


def _lead(**kwargs) -> CrmLead:
    defaults = dict(
        name="Asha Traders",
        phone="9876543210",
        city="Chennai",
        source="Walk-in",
        status=LeadStatus.NEW.value,
        priority="High",
        estimated_value=75000.0,
        assigned_user_id="u1",
        assigned_user_name="Ravi",
    )
    defaults.update(kwargs)
    return CrmLead(**defaults)


def _enquiry(**kwargs) -> CrmEnquiry:
    defaults = dict(
        enquiry_number="ENQ-001",
        party_name="Asha Traders",
        product_interest="Cotton sarees",
        status=EnquiryStatus.OPEN.value,
        priority="Medium",
        estimated_value=25000.0,
        assigned_user_id="u1",
    )
    defaults.update(kwargs)
    return CrmEnquiry(**defaults)


def _activity(**kwargs) -> CrmActivity:
    defaults = dict(
        activity_type="Called",
        party_name="Asha Traders",
        status=ActivityStatus.SCHEDULED.value,
        priority="Medium",
        assigned_user_id="u1",
        scheduled_at=datetime.combine(TODAY, datetime.min.time()).replace(hour=10),
    )
    defaults.update(kwargs)
    return CrmActivity(**defaults)


# --- list schemas ------------------------------------------------------------
@pytest.mark.parametrize("entity_key", sorted(SCHEMAS))
def test_schema_entity_keys_are_namespaced(entity_key):
    assert entity_key.startswith("crm_")
    schema = SCHEMAS[entity_key]
    assert schema.filter_fields
    assert schema.sort_options


def test_default_filters_return_every_lead():
    leads = [_lead(), _lead(name="Bala Textiles", assigned_user_id="")]
    result = F.apply_filters(leads, CRM_LEADS, F.default_filters(CRM_LEADS))
    assert len(result) == len(leads)


def test_lead_search_matches_phone_and_city():
    leads = [_lead(), _lead(name="Bala Textiles", phone="9000000000", city="Madurai")]
    filters = F.default_filters(CRM_LEADS)
    filters["search"] = "madurai"
    assert [l.name for l in F.apply_filters(leads, CRM_LEADS, filters)] == [
        "Bala Textiles"
    ]

    filters["search"] = "9876543210"
    assert [l.name for l in F.apply_filters(leads, CRM_LEADS, filters)] == [
        "Asha Traders"
    ]


def test_lead_assignment_and_status_filters():
    leads = [_lead(), _lead(name="Unowned", assigned_user_id="", assigned_user_name="")]
    filters = F.default_filters(CRM_LEADS)
    filters["assignment"] = "unassigned"
    assert [l.name for l in F.apply_filters(leads, CRM_LEADS, filters)] == ["Unowned"]

    filters = F.default_filters(CRM_LEADS)
    filters["statuses"] = [LeadStatus.LOST.value]
    assert F.apply_filters(leads, CRM_LEADS, filters) == []


def test_lead_follow_up_filter_splits_overdue_and_today():
    overdue = _lead(
        name="Overdue",
        next_follow_up_at=datetime.combine(
            TODAY - timedelta(days=2), datetime.min.time()
        ),
    )
    due_today = _lead(
        name="Today",
        next_follow_up_at=datetime.combine(TODAY, datetime.min.time()),
    )
    unscheduled = _lead(name="None")
    leads = [overdue, due_today, unscheduled]

    for value, expected in (
        ("overdue", ["Overdue"]),
        ("today", ["Today"]),
        ("none", ["None"]),
    ):
        filters = F.default_filters(CRM_LEADS)
        filters["follow_up"] = value
        assert [l.name for l in F.apply_filters(leads, CRM_LEADS, filters)] == expected


def test_enquiry_and_activity_search_filters():
    enquiries = [_enquiry(), _enquiry(party_name="Bala", product_interest="Silk")]
    filters = F.default_filters(CRM_ENQUIRIES)
    filters["search"] = "silk"
    assert len(F.apply_filters(enquiries, CRM_ENQUIRIES, filters)) == 1

    activities = [_activity(), _activity(activity_type="Meeting")]
    filters = F.default_filters(CRM_ACTIVITIES)
    filters["activity_types"] = ["Meeting"]
    assert len(F.apply_filters(activities, CRM_ACTIVITIES, filters)) == 1


def test_activity_due_filter_only_counts_open_activities():
    past = datetime.combine(TODAY - timedelta(days=1), datetime.min.time())
    activities = [
        _activity(scheduled_at=past),
        _activity(scheduled_at=past, status=ActivityStatus.COMPLETED.value),
    ]
    filters = F.default_filters(CRM_ACTIVITIES)
    filters["due"] = "overdue"
    assert len(F.apply_filters(activities, CRM_ACTIVITIES, filters)) == 1


def test_lead_sort_by_estimated_value():
    leads = [_lead(estimated_value=1000.0), _lead(name="Big", estimated_value=90000.0)]
    ordered = F.sort_records(
        leads, CRM_LEADS, {"key": "estimated_value", "desc": True}
    )
    assert ordered[0].name == "Big"


def test_report_filter_schema_exposes_common_fields():
    keys = {field.key for field in CRM_REPORT_FILTERS.filter_fields}
    assert {
        "date_range",
        "assigned_user_id",
        "customer_id",
        "activity_type",
        "inactivity_days",
        "high_value_threshold",
    } <= keys


# --- calendar events ---------------------------------------------------------
def test_activity_maps_to_timed_event():
    activity = _activity(
        scheduled_at=datetime(2026, 5, 12, 9, 30), id="act-1", party_name="Asha"
    )
    event = activity_to_event(activity, now=NOW)
    assert event["id"] == "act-1"
    assert event["allDay"] is False
    assert event["start"] == "2026-05-12T09:30:00"
    assert event["end"] == (
        datetime(2026, 5, 12, 9, 30) + timedelta(minutes=DEFAULT_DURATION_MINUTES)
    ).isoformat(timespec="seconds")
    assert "Asha" in event["title"]
    assert event["extendedProps"]["status"] == ActivityStatus.SCHEDULED.value


def test_activity_at_is_used_when_nothing_is_scheduled():
    activity = _activity(
        scheduled_at=None, activity_at=datetime(2026, 5, 12, 15, 0)
    )
    event = activity_to_event(activity, now=NOW)
    assert event["start"] == "2026-05-12T15:00:00"


def test_open_activity_in_the_past_is_coloured_overdue():
    overdue = activity_to_event(
        _activity(scheduled_at=datetime(2026, 5, 11, 9, 0)), now=NOW
    )
    assert overdue["backgroundColor"] == OVERDUE_COLOR

    completed = activity_to_event(
        _activity(
            scheduled_at=datetime(2026, 5, 11, 9, 0),
            status=ActivityStatus.COMPLETED.value,
        ),
        now=NOW,
    )
    assert completed["backgroundColor"] == STATUS_COLORS[ActivityStatus.COMPLETED.value]


def test_activity_without_a_date_is_skipped():
    assert activity_to_event(_activity(scheduled_at=None, activity_at=None)) is None
    events = activities_to_events(
        [_activity(), _activity(scheduled_at=None, activity_at=None)], now=NOW
    )
    assert len(events) == 1


def test_activities_to_events_handles_empty_input():
    assert activities_to_events([]) == []
    assert activities_to_events(None) == []


# --- WhatsApp reminder -------------------------------------------------------
def test_reminder_draft_builds_click_to_chat_url():
    draft = build_reminder_draft(
        customer_id="c1",
        customer_name="Asha Traders",
        phone="9876543210",
        outstanding_amount=15000,
        business_name="VayBooks",
    )
    assert draft.whatsapp_url.startswith("https://wa.me/919876543210?text=")
    assert "Asha Traders" in draft.message
    assert "VayBooks" in draft.message
    assert "15,000.00" in draft.message
    assert " " not in draft.whatsapp_url


def test_reminder_draft_honours_message_override():
    draft = build_reminder_draft(
        customer_id="c1",
        customer_name="Asha",
        phone="09876543210",
        outstanding_amount=100,
        message_override="Custom text",
    )
    assert draft.message == "Custom text"
    assert draft.whatsapp_url == "https://wa.me/919876543210?text=Custom%20text"


def test_reminder_draft_rejects_an_invalid_number():
    from vaybooks.bms.domain.shared.exceptions import ValidationError

    with pytest.raises(ValidationError):
        build_reminder_draft(
            customer_id="c1",
            customer_name="Asha",
            phone="",
            outstanding_amount=100,
        )


# --- adapter empty states ----------------------------------------------------
def test_adapter_reports_unavailable_without_services():
    adapter = CrmAdapter({})
    assert adapter.available is False
    assert adapter.list_leads() == []
    assert adapter.list_enquiries() == []
    assert adapter.list_activities() == []
    assert adapter.timeline(lead_id="x") == []
    assert adapter.get_lead("x") is None
    assert adapter.get_enquiry("x") is None
    assert adapter.get_activity("x") is None
    assert adapter.dashboard_snapshot() is None
    assert adapter.get_settings() is None
    assert adapter.owners() == []
    assert adapter.list_notifications("u1") == []


def test_adapter_writes_raise_when_unwired():
    adapter = CrmAdapter({})
    with pytest.raises(CrmUnavailable):
        adapter.create_lead({"name": "Asha"})
    with pytest.raises(CrmUnavailable):
        adapter.create_enquiry({"party_name": "Asha"})
    with pytest.raises(CrmUnavailable):
        adapter.complete_activity("a1")


def test_adapter_lists_all_34_reports_without_a_backend():
    catalog = CrmAdapter({}).list_reports()
    assert len(catalog) == len(CRM_REPORT_DEFINITIONS) == 34
    assert {row["id"] for row in catalog} == {
        report_id for report_id, _title, _cat in CRM_REPORT_DEFINITIONS
    }


def test_adapter_read_degrades_when_a_service_raises():
    class Boom:
        def list_leads(self, **_kwargs):
            raise RuntimeError("backend down")

    adapter = CrmAdapter({"crm_leads": Boom()})
    assert adapter.available is True
    assert adapter.list_leads() == []


def test_adapter_resolves_alternate_method_names():
    class Legacy:
        def list(self, **_kwargs):
            return [_lead(name="Legacy")]

    adapter = CrmAdapter({"crm_leads": Legacy()})
    assert [lead.name for lead in adapter.list_leads()] == ["Legacy"]


# --- exports -----------------------------------------------------------------
def test_lead_csv_export_has_a_header_and_one_row_per_lead():
    csv_bytes = records_to_csv([_lead()], LEAD_EXPORT_COLUMNS)
    lines = csv_bytes.decode("utf-8").strip().splitlines()
    assert lines[0].startswith("Lead Number,Name")
    assert len(lines) == 2
    assert "Asha Traders" in lines[1]


def test_activity_csv_export_formats_datetimes():
    activity = _activity(scheduled_at=datetime(2026, 5, 12, 9, 30))
    body = records_to_csv([activity], ACTIVITY_EXPORT_COLUMNS).decode("utf-8")
    assert "2026-05-12 09:30" in body


def test_report_rows_export_follows_the_column_order():
    body = rows_to_csv(
        [{"customer_name": "Asha", "total": 3}], ["total", "customer_name"]
    ).decode("utf-8")
    assert body.splitlines()[0] == "total,customer_name"
    assert body.splitlines()[1] == "3,Asha"


def test_empty_export_still_writes_the_header():
    body = records_to_csv([], LEAD_EXPORT_COLUMNS).decode("utf-8")
    assert body.strip().count("\n") == 0
