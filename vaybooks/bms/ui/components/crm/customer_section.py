"""CRM block embedded in the customer detail page.

Renders nothing when CRM services are not wired, so the customer page keeps
working on installations without the CRM module.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.crm import dialogs
from vaybooks.bms.ui.components.crm.common import (
    fmt_datetime,
    fmt_money,
    owner_label,
    page_adapter,
    status_color,
)
from vaybooks.bms.ui.components.crm.timeline import render_timeline
from vaybooks.bms.ui.components.crm.whatsapp import (
    arm_reminder_dialog,
    open_reminder_dialog_if_armed,
)
from vaybooks.bms.ui.crm_adapters import field, record_id, text
from vaybooks.bms.ui.styles import status_badge

TIMELINE_LIMIT = 15


def _quick_actions(customer, adapter) -> None:
    customer_id = text(field(customer, "id"))
    party_name = text(field(customer, "customer_name"))
    activity_actions = (
        ("Record Call", "Called"),
        ("Record Visit", "Sales Representative Visit"),
        ("Contact for Order", "Contacted for Order"),
        ("Contact for Credit", "Contacted for Credit"),
        ("Schedule Follow-up", "Follow-up Scheduled"),
    )
    row = st.columns(5)
    for index, (label, activity_type) in enumerate(activity_actions):
        if row[index].button(
            label,
            key=f"cd_crm_activity_{index}",
            width="stretch",
        ):
            dialogs.arm(
                dialogs.ACTIVITY_ADD,
                {
                    "customer_id": customer_id,
                    "party_name": party_name,
                    "activity_type": activity_type,
                },
            )
            st.rerun()

    row = st.columns(4)
    if row[0].button("Create Enquiry", key="cd_crm_enquiry", width="stretch"):
        dialogs.arm(
            dialogs.ENQUIRY_ADD,
            {"customer_id": customer_id, "party_name": party_name},
        )
        st.rerun()
    if row[1].button("Create Quotation", key="cd_crm_quotation", width="stretch"):
        navigation.go_to_list("quotations_list", customer_id=customer_id)
    if row[2].button(
        "View Outstanding",
        key="cd_crm_outstanding",
        width="stretch",
    ):
        navigation.go_to_list("sales_invoices_list", customer_id=customer_id)
    if row[3].button(
        ":material/chat: WhatsApp Reminder",
        key="cd_crm_whatsapp",
        width="stretch",
        help="Draft a payment reminder and open WhatsApp click-to-chat.",
    ):
        arm_reminder_dialog(customer_id)
        st.rerun()


def _enquiries(customer_id: str, adapter) -> None:
    enquiries = adapter.enquiries_for(customer_id=customer_id)
    st.markdown(f"**Enquiries ({len(enquiries)})**")
    if not enquiries:
        st.caption("No enquiries recorded for this customer.")
        return
    for enquiry in enquiries[:5]:
        cols = st.columns([3, 2, 1], vertical_alignment="center")
        cols[0].write(
            text(field(enquiry, "product_interest"))
            or text(field(enquiry, "enquiry_number"), default="Enquiry")
        )
        status = text(field(enquiry, "status"))
        cols[1].markdown(
            status_badge(status, status_color(status), compact=True),
            unsafe_allow_html=True,
        )
        if cols[2].button("Open", key=f"cd_crm_enq_{record_id(enquiry)}"):
            navigation.go_to_detail("crm_enquiry_detail", record_id(enquiry))
    if len(enquiries) > 5:
        st.caption(f"+ {len(enquiries) - 5} more")


def _source_leads(customer_id: str, adapter) -> None:
    leads = adapter.leads_for_customer(customer_id)
    if not leads:
        return
    st.markdown("**Originating leads**")
    for lead in leads[:5]:
        cols = st.columns([3, 2, 1], vertical_alignment="center")
        cols[0].write(text(field(lead, "name"), default="Lead"))
        cols[1].caption(
            " · ".join(
                part
                for part in (
                    text(field(lead, "source")),
                    fmt_money(field(lead, "estimated_value")),
                )
                if part and part != "—"
            )
        )
        if cols[2].button("Open", key=f"cd_crm_lead_{record_id(lead)}"):
            navigation.go_to_detail("crm_lead_detail", record_id(lead))


def _next_action(activities: list) -> str:
    upcoming = [
        activity
        for activity in activities
        if field(activity, "scheduled_at") is not None
        and text(field(activity, "status")) in ("Scheduled", "In Progress")
    ]
    if not upcoming:
        return "—"
    nearest = min(upcoming, key=lambda a: field(a, "scheduled_at"))
    return (
        f"{text(field(nearest, 'activity_type'), default='Activity')} · "
        f"{fmt_datetime(field(nearest, 'scheduled_at'))}"
    )


def _customer_snapshot(
    services: dict, customer_id: str, activities: list, enquiries: list
) -> list[tuple[str, str]]:
    def latest(activity_type: str) -> str:
        values = [
            field(activity, "activity_at", "completed_at", "scheduled_at")
            for activity in activities
            if text(field(activity, "activity_type")) == activity_type
        ]
        values = [value for value in values if value is not None]
        return fmt_datetime(max(values)) if values else "—"

    manual_contacts = [
        field(activity, "activity_at", "completed_at")
        for activity in activities
        if text(field(activity, "origin")) != "Automatic"
        and field(activity, "activity_at", "completed_at") is not None
    ]
    sales = services.get("sales")
    try:
        orders = [
            order
            for order in (sales.list_sales_orders() if sales else [])
            if text(field(order, "customer_id")) == customer_id
        ]
    except Exception:
        orders = []
    try:
        quotations = [
            quotation
            for quotation in (sales.list_quotations() if sales else [])
            if text(field(quotation, "customer_id")) == customer_id
            and text(field(quotation, "status")) in {"Draft", "Sent"}
        ]
    except Exception:
        quotations = []
    accounting = services.get("accounting")
    try:
        outstanding = float(
            (accounting.customer_balances_by_customer() or {}).get(customer_id, 0)
        )
    except Exception:
        outstanding = 0.0
    last_order = max(
        (field(order, "order_date", "created_at") for order in orders),
        default=None,
    )
    open_enquiries = sum(
        1
        for enquiry in enquiries
        if text(field(enquiry, "status")) not in {"Won", "Lost", "Closed"}
    )
    return [
        (
            "Last contact",
            fmt_datetime(max(manual_contacts)) if manual_contacts else "—",
        ),
        ("Last visit", latest("Sales Representative Visit")),
        ("Last order", fmt_datetime(last_order)),
        ("Last payment", latest("Payment Received")),
        ("Next follow-up", _next_action(activities)),
        ("Outstanding", fmt_money(outstanding, "₹0")),
        ("Open enquiries", str(open_enquiries)),
        ("Active quotations", str(len(quotations))),
    ]


def render_customer_crm_section(services: dict, customer: Any) -> None:
    """Render the CRM panel for ``customer``; no-op without CRM services."""
    adapter = page_adapter(services)
    if not adapter.available:
        return

    customer_id = text(field(customer, "id"))
    activities = adapter.timeline(customer_id=customer_id, limit=100)
    enquiries = adapter.enquiries_for(customer_id=customer_id)

    with st.container(border=True):
        st.subheader("CRM")
        st.caption(f"Assigned representative: {owner_label(customer)}")
        snapshot = _customer_snapshot(
            services, customer_id, activities, enquiries
        )
        for start in range(0, len(snapshot), 4):
            summary = st.columns(4)
            for col, (label, value) in zip(summary, snapshot[start : start + 4]):
                col.metric(label, value)

        _quick_actions(customer, adapter)
        _enquiries(customer_id, adapter)
        _source_leads(customer_id, adapter)

        st.markdown("**Activity timeline**")
        render_timeline(
            activities,
            limit=TIMELINE_LIMIT,
            empty_text="No CRM activity recorded for this customer yet.",
        )

    dialogs.open_activity_dialogs_if_armed(adapter, services)
    dialogs.open_enquiry_dialogs_if_armed(adapter, services)
    open_reminder_dialog_if_armed(services, adapter)
