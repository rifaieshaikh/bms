"""List schemas for the CRM module (leads, enquiries, activities, reports).

Catalog-backed dropdowns (sources, statuses, outcomes, owners) load from CRM
settings at render time, so option loaders are registered into the shared
``OPTION_LOADERS`` registry rather than hard-coded here.
"""

from __future__ import annotations

from datetime import date, timedelta

from vaybooks.bms.domain.crm.enums import (
    ActivityStatus,
    DEFAULT_ACTIVITY_OUTCOMES,
    DEFAULT_ACTIVITY_TYPES,
    DEFAULT_LEAD_SOURCES,
    DEFAULT_LOST_REASONS,
    EnquiryStatus,
    LeadPriority,
    LeadStatus,
)
from vaybooks.bms.ui import list_schemas
from vaybooks.bms.ui.crm_adapters import CrmAdapter, field, text
from vaybooks.bms.ui.list_schemas import F, FilterField, ListSchema, SortOption
from vaybooks.bms.ui.pagination import CARD_PAGE_SIZE

LEAD_STATUSES = tuple(s.value for s in LeadStatus)
ENQUIRY_STATUSES = tuple(s.value for s in EnquiryStatus)
ACTIVITY_STATUSES = tuple(s.value for s in ActivityStatus)
PRIORITIES = tuple(p.value for p in LeadPriority)

OPEN_LEAD_STATUSES = (
    LeadStatus.NEW.value,
    LeadStatus.CONTACTED.value,
    LeadStatus.QUALIFIED.value,
    LeadStatus.FOLLOW_UP_REQUIRED.value,
    LeadStatus.INTERESTED.value,
    LeadStatus.ON_HOLD.value,
)

OPEN_ENQUIRY_STATUSES = (
    EnquiryStatus.OPEN.value,
    EnquiryStatus.ASSIGNED.value,
    EnquiryStatus.IN_PROGRESS.value,
    EnquiryStatus.QUOTATION_REQUIRED.value,
    EnquiryStatus.QUOTATION_SENT.value,
    EnquiryStatus.NEGOTIATION.value,
    EnquiryStatus.ON_HOLD.value,
)

OPEN_ACTIVITY_STATUSES = (
    ActivityStatus.SCHEDULED.value,
    ActivityStatus.IN_PROGRESS.value,
)


def _opts(values) -> list[tuple]:
    return [(v, v) for v in values]


def _last_90_days() -> tuple[date, date]:
    today = date.today()
    return today - timedelta(days=89), today


# --- option loaders ----------------------------------------------------------
def _catalog_labels(services, attribute: str, fallback) -> list[tuple]:
    """Active labels from a CRM settings catalog, else the seeded defaults."""
    settings = CrmAdapter(services).get_settings()
    items = (
        settings.get(attribute)
        if isinstance(settings, dict)
        else getattr(settings, attribute, None)
        if settings is not None
        else None
    )
    labels = [
        text(item.get("label"))
        for item in items or []
        if isinstance(item, dict) and item.get("active", True) and item.get("label")
    ]
    return _opts(labels or fallback)


def _crm_lead_sources(services):
    return _catalog_labels(services, "lead_sources", DEFAULT_LEAD_SOURCES)


def _crm_activity_types(services):
    return _catalog_labels(services, "activity_types", DEFAULT_ACTIVITY_TYPES)


def _crm_activity_outcomes(services):
    return _catalog_labels(services, "activity_outcomes", DEFAULT_ACTIVITY_OUTCOMES)


def _crm_lost_reasons(services):
    return _catalog_labels(services, "lost_reasons", DEFAULT_LOST_REASONS)


def _crm_owners(services):
    return CrmAdapter(services).owners()


CRM_OPTION_LOADERS = {
    "crm_lead_sources": _crm_lead_sources,
    "crm_activity_types": _crm_activity_types,
    "crm_activity_outcomes": _crm_activity_outcomes,
    "crm_lost_reasons": _crm_lost_reasons,
    "crm_owners": _crm_owners,
}

# Registered on import so the shared filter bar can resolve CRM dropdowns.
list_schemas.OPTION_LOADERS.update(CRM_OPTION_LOADERS)


# --- custom match predicates -------------------------------------------------
def _match_unassigned(record, value) -> bool:
    assigned = bool(text(field(record, "assigned_user_id")))
    return (not assigned) if value == "unassigned" else assigned


def _match_lead_search(lead, value) -> bool:
    needle = str(value).strip().casefold()
    if not needle:
        return True
    haystack = " ".join(
        text(field(lead, name))
        for name in (
            "name",
            "lead_number",
            "phone",
            "alternate_phone",
            "email",
            "contact_person",
            "city",
            "area",
            "gstin",
            "interested_products",
        )
    )
    return needle in haystack.casefold()


def _match_enquiry_search(enquiry, value) -> bool:
    needle = str(value).strip().casefold()
    if not needle:
        return True
    haystack = " ".join(
        text(field(enquiry, name))
        for name in (
            "enquiry_number",
            "party_name",
            "product_interest",
            "description",
            "source",
        )
    )
    return needle in haystack.casefold()


def _match_activity_search(activity, value) -> bool:
    needle = str(value).strip().casefold()
    if not needle:
        return True
    haystack = " ".join(
        text(field(activity, name))
        for name in (
            "activity_type",
            "party_name",
            "notes",
            "outcome",
            "next_action",
            "location",
            "assigned_user_name",
        )
    )
    return needle in haystack.casefold()


def _match_lead_due(lead, value) -> bool:
    due = field(lead, "next_follow_up_at")
    due_date = due.date() if hasattr(due, "date") else due
    today = date.today()
    if value == "none":
        return due_date is None
    if due_date is None:
        return False
    if value == "overdue":
        return due_date < today
    if value == "today":
        return due_date == today
    if value == "week":
        return today <= due_date <= today + timedelta(days=7)
    return True


def _match_activity_due(activity, value) -> bool:
    scheduled = field(activity, "scheduled_at")
    scheduled_date = scheduled.date() if hasattr(scheduled, "date") else scheduled
    today = date.today()
    if scheduled_date is None:
        return False
    open_now = text(field(activity, "status")) in OPEN_ACTIVITY_STATUSES
    if value == "overdue":
        return open_now and scheduled_date < today
    if value == "today":
        return scheduled_date == today
    if value == "week":
        return today <= scheduled_date <= today + timedelta(days=7)
    if value == "past":
        return scheduled_date < today
    return True


def _match_origin(activity, value) -> bool:
    return text(field(activity, "origin")).casefold() == str(value).casefold()


def _match_converted(lead, value) -> bool:
    linked = bool(text(field(lead, "customer_id")))
    return linked if value == "linked" else (not linked)


# --- schemas -----------------------------------------------------------------
CRM_LEADS = ListSchema(
    entity_key="crm_leads",
    title="Leads",
    filter_fields=[
        FilterField(
            "search",
            "Search",
            F.EXACT,
            match=_match_lead_search,
            placeholder="name, phone, email, city…",
            help="Matches name, number, phone, email, contact, city, area, GSTIN.",
        ),
        FilterField(
            "statuses",
            "Status",
            F.MULTISELECT,
            record_attr="status",
            options=_opts(LEAD_STATUSES),
        ),
        FilterField(
            "priorities",
            "Priority",
            F.MULTISELECT,
            record_attr="priority",
            options=_opts(PRIORITIES),
        ),
        FilterField(
            "source",
            "Source",
            F.ENTITY_SELECT,
            options_loader="crm_lead_sources",
            all_label="All sources",
        ),
        FilterField(
            "assigned_user_id",
            "Owner",
            F.ENTITY_SELECT,
            options_loader="crm_owners",
            all_label="All owners",
        ),
        FilterField(
            "assignment",
            "Assignment",
            F.SELECT,
            options=[("unassigned", "Unassigned"), ("assigned", "Assigned")],
            multi=False,
            match=_match_unassigned,
        ),
        FilterField(
            "follow_up",
            "Follow-up",
            F.SELECT,
            options=[
                ("overdue", "Overdue"),
                ("today", "Due today"),
                ("week", "Next 7 days"),
                ("none", "Not scheduled"),
            ],
            multi=False,
            match=_match_lead_due,
        ),
        FilterField("created_at", "Created", F.DATE_RANGE),
        FilterField("city", "City", F.REGEX),
        FilterField("area", "Area", F.REGEX),
        FilterField(
            "min_value", "Min estimated value", F.NUMBER_MIN, record_attr="estimated_value"
        ),
        FilterField(
            "customer_link",
            "Customer link",
            F.SELECT,
            options=[("linked", "Linked to customer"), ("unlinked", "Not linked")],
            multi=False,
            match=_match_converted,
        ),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("updated_at", "Last updated"),
        SortOption("name", "Lead name"),
        SortOption("status", "Status"),
        SortOption("priority", "Priority"),
        SortOption("estimated_value", "Estimated value"),
        SortOption("next_follow_up_at", "Next follow-up"),
        SortOption("last_activity_at", "Last activity"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

CRM_ENQUIRIES = ListSchema(
    entity_key="crm_enquiries",
    title="Enquiries",
    filter_fields=[
        FilterField(
            "search",
            "Search",
            F.EXACT,
            match=_match_enquiry_search,
            placeholder="enquiry number, party, product…",
        ),
        FilterField(
            "statuses",
            "Status",
            F.MULTISELECT,
            record_attr="status",
            options=_opts(ENQUIRY_STATUSES),
        ),
        FilterField(
            "priorities",
            "Priority",
            F.MULTISELECT,
            record_attr="priority",
            options=_opts(PRIORITIES),
        ),
        FilterField(
            "source",
            "Source",
            F.ENTITY_SELECT,
            options_loader="crm_lead_sources",
            all_label="All sources",
        ),
        FilterField(
            "assigned_user_id",
            "Owner",
            F.ENTITY_SELECT,
            options_loader="crm_owners",
            all_label="All owners",
        ),
        FilterField(
            "assignment",
            "Assignment",
            F.SELECT,
            options=[("unassigned", "Unassigned"), ("assigned", "Assigned")],
            multi=False,
            match=_match_unassigned,
        ),
        FilterField("enquiry_date", "Enquiry date", F.DATE_RANGE),
        FilterField("expected_decision_at", "Expected decision", F.DATE_RANGE),
        FilterField(
            "min_value", "Min estimated value", F.NUMBER_MIN, record_attr="estimated_value"
        ),
    ],
    sort_options=[
        SortOption("created_at", "Created"),
        SortOption("enquiry_date", "Enquiry date"),
        SortOption("enquiry_number", "Enquiry number"),
        SortOption("party_name", "Party"),
        SortOption("status", "Status"),
        SortOption("estimated_value", "Estimated value"),
        SortOption("expected_decision_at", "Expected decision"),
    ],
    default_sort="created_at",
    page_size=CARD_PAGE_SIZE,
)

CRM_ACTIVITIES = ListSchema(
    entity_key="crm_activities",
    title="Activities",
    filter_fields=[
        FilterField(
            "search",
            "Search",
            F.EXACT,
            match=_match_activity_search,
            placeholder="party, notes, outcome…",
        ),
        FilterField(
            "activity_types",
            "Activity type",
            F.MULTISELECT,
            record_attr="activity_type",
            options=_opts(DEFAULT_ACTIVITY_TYPES),
        ),
        FilterField(
            "statuses",
            "Status",
            F.MULTISELECT,
            record_attr="status",
            options=_opts(ACTIVITY_STATUSES),
        ),
        FilterField(
            "outcome",
            "Outcome",
            F.ENTITY_SELECT,
            options_loader="crm_activity_outcomes",
            all_label="All outcomes",
        ),
        FilterField(
            "assigned_user_id",
            "Owner",
            F.ENTITY_SELECT,
            options_loader="crm_owners",
            all_label="All owners",
        ),
        FilterField(
            "due",
            "Due",
            F.SELECT,
            options=[
                ("overdue", "Overdue"),
                ("today", "Today"),
                ("week", "Next 7 days"),
                ("past", "Past"),
            ],
            multi=False,
            match=_match_activity_due,
        ),
        FilterField("scheduled_at", "Scheduled", F.DATE_RANGE),
        FilterField(
            "origin",
            "Origin",
            F.SELECT,
            options=[("Manual", "Manual"), ("Automatic", "Automatic")],
            multi=False,
            match=_match_origin,
        ),
        FilterField(
            "priorities",
            "Priority",
            F.MULTISELECT,
            record_attr="priority",
            options=_opts(PRIORITIES),
        ),
    ],
    sort_options=[
        SortOption("scheduled_at", "Scheduled"),
        SortOption("activity_at", "Activity date"),
        SortOption("created_at", "Created"),
        SortOption("activity_type", "Activity type"),
        SortOption("status", "Status"),
        SortOption("priority", "Priority"),
        SortOption("party_name", "Party"),
    ],
    default_sort="scheduled_at",
    page_size=CARD_PAGE_SIZE,
)

# Shared filter set for the CRM report runner. Reports are served by the
# backend engine, so these map onto ``CrmReportFilters`` instead of being
# applied client-side.
CRM_REPORT_FILTERS = ListSchema(
    entity_key="crm_reports",
    title="CRM Reports",
    filter_fields=[
        FilterField("date_range", "Period", F.DATE_RANGE, default=_last_90_days),
        FilterField(
            "assigned_user_id",
            "Sales representative",
            F.ENTITY_SELECT,
            options_loader="crm_owners",
            multi=False,
            all_label="All representatives",
        ),
        FilterField(
            "customer_id",
            "Customer",
            F.ENTITY_SELECT,
            options_loader="customers",
            multi=False,
            all_label="All customers",
        ),
        FilterField(
            "activity_type",
            "Activity type",
            F.ENTITY_SELECT,
            options_loader="crm_activity_types",
            multi=False,
            all_label="All activity types",
        ),
        FilterField("area", "Area", F.EXACT),
        FilterField("branch", "Branch", F.EXACT),
        FilterField(
            "inactivity_days",
            "Inactivity window (days)",
            F.NUMBER_MIN,
            help="Used by dormancy, no-activity, and declining-frequency reports.",
        ),
        FilterField(
            "high_value_threshold",
            "High-value threshold (₹)",
            F.NUMBER_MIN,
            help="Used by the high-value lead and customer reports.",
        ),
    ],
    sort_options=[SortOption("date_range", "Period")],
    default_sort="date_range",
)

SCHEMAS = {
    schema.entity_key: schema
    for schema in (CRM_LEADS, CRM_ENQUIRIES, CRM_ACTIVITIES, CRM_REPORT_FILTERS)
}
