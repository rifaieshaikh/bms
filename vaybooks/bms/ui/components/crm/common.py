"""Shared CRM presentation helpers: badges, dates, catalog options."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional, Sequence

import streamlit as st

from vaybooks.bms.domain.crm.enums import (
    ActivityStatus,
    DEFAULT_ACTIVITY_OUTCOMES,
    DEFAULT_ACTIVITY_TYPES,
    DEFAULT_LEAD_SOURCES,
    DEFAULT_LOST_REASONS,
    EnquiryStatus,
    LeadStatus,
)
from vaybooks.bms.ui.auth.session import current_user_id, current_user_name
from vaybooks.bms.ui.crm_adapters import CrmAdapter, field, text

CRM_UNAVAILABLE_TEXT = (
    "The CRM module is not available yet. Once CRM services are enabled, "
    "leads, enquiries, activities and reports appear here."
)

STATUS_COLORS: dict[str, str] = {
    LeadStatus.NEW.value: "blue",
    LeadStatus.CONTACTED.value: "blue",
    LeadStatus.QUALIFIED.value: "violet",
    LeadStatus.FOLLOW_UP_REQUIRED.value: "orange",
    LeadStatus.INTERESTED.value: "green",
    LeadStatus.NOT_INTERESTED.value: "gray",
    LeadStatus.CONVERTED.value: "green",
    LeadStatus.LOST.value: "red",
    LeadStatus.ON_HOLD.value: "gray",
    EnquiryStatus.OPEN.value: "blue",
    EnquiryStatus.ASSIGNED.value: "blue",
    EnquiryStatus.IN_PROGRESS.value: "violet",
    EnquiryStatus.QUOTATION_REQUIRED.value: "orange",
    EnquiryStatus.QUOTATION_SENT.value: "violet",
    EnquiryStatus.NEGOTIATION.value: "orange",
    EnquiryStatus.WON.value: "green",
    ActivityStatus.SCHEDULED.value: "blue",
    ActivityStatus.COMPLETED.value: "green",
    ActivityStatus.CANCELLED.value: "gray",
    ActivityStatus.MISSED.value: "red",
    ActivityStatus.REVERSED.value: "gray",
}

PRIORITY_COLORS = {
    "Low": "gray",
    "Medium": "blue",
    "High": "orange",
    "Urgent": "red",
}


def status_color(label: str) -> str:
    return STATUS_COLORS.get(text(label), "plum")


def priority_color(label: str) -> str:
    return PRIORITY_COLORS.get(text(label), "gray")


def fmt_date(value: Any, default: str = "—") -> str:
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return default


def fmt_datetime(value: Any, default: str = "—") -> str:
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return default


def fmt_money(value: Any, default: str = "—") -> str:
    try:
        amount = float(value or 0)
    except (TypeError, ValueError):
        return default
    if not amount:
        return default
    return f"\u20b9{amount:,.0f}"


def days_overdue(value: Any, *, today: Optional[date] = None) -> int:
    """Whole days a due date is in the past; 0 when future or unset."""
    due = value.date() if isinstance(value, datetime) else value
    if not isinstance(due, date):
        return 0
    delta = (today or date.today()) - due
    return max(delta.days, 0)


def catalog_options(
    adapter: CrmAdapter, attribute: str, fallback: Sequence[str]
) -> list[str]:
    """Active labels from a CRM settings catalog, falling back to defaults."""
    settings = adapter.get_settings()
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
    return labels or list(fallback)


def lead_sources(adapter: CrmAdapter) -> list[str]:
    return catalog_options(adapter, "lead_sources", DEFAULT_LEAD_SOURCES)


def activity_types(adapter: CrmAdapter) -> list[str]:
    return catalog_options(adapter, "activity_types", DEFAULT_ACTIVITY_TYPES)


def activity_outcomes(adapter: CrmAdapter) -> list[str]:
    return catalog_options(adapter, "activity_outcomes", DEFAULT_ACTIVITY_OUTCOMES)


def lost_reasons(adapter: CrmAdapter) -> list[str]:
    return catalog_options(adapter, "lost_reasons", DEFAULT_LOST_REASONS)


def owner_label(record: Any) -> str:
    return text(
        field(record, "assigned_user_name", "assigned_user_id"), default="Unassigned"
    )


def index_of(options: Sequence[str], value: Any, default: int = 0) -> int:
    needle = text(value)
    return options.index(needle) if needle in options else default


def page_adapter(services: dict) -> CrmAdapter:
    """Adapter stamped with the signed-in user for audit trails."""
    return CrmAdapter(
        services, actor_id=current_user_id(), actor_name=current_user_name()
    )


def crm_page_adapter(services: dict) -> Optional[CrmAdapter]:
    """Adapter for a CRM page, or ``None`` after rendering the empty state."""
    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return None
    return adapter
