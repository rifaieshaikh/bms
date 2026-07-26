"""CRM lead detail route (`?id=<lead_id>`): profile, actions, timeline."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.crm.enums import LeadStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.crm import dialogs
from vaybooks.bms.ui.components.crm.common import (
    CRM_UNAVAILABLE_TEXT,
    fmt_datetime,
    fmt_money,
    owner_label,
    page_adapter,
    priority_color,
    status_color,
)
from vaybooks.bms.ui.components.crm.timeline import render_timeline
from vaybooks.bms.ui.crm_adapters import field, record_id, text
from vaybooks.bms.ui.styles import metric_grid, panel, status_badge

PAGE_KEY = "crm_lead_detail"


def _header(lead) -> None:
    title_col, badge_col = st.columns([3, 2], vertical_alignment="center")
    with title_col:
        st.title(text(field(lead, "name"), default="Lead"))
        number = text(field(lead, "lead_number"))
        if number:
            st.caption(number)
    with badge_col:
        status = text(field(lead, "status"))
        priority = text(field(lead, "priority"))
        st.markdown(
            status_badge(status, status_color(status))
            + " "
            + status_badge(priority, priority_color(priority)),
            unsafe_allow_html=True,
        )
    if status == LeadStatus.LOST.value:
        st.error(
            f"Lost — {text(field(lead, 'lost_reason'), default='no reason recorded')}"
        )


def _profile(lead) -> None:
    with st.container(border=True):
        cols = st.columns(3)
        cols[0].write(f"**Phone:** {text(field(lead, 'phone'), default='—')}")
        cols[1].write(f"**Alt:** {text(field(lead, 'alternate_phone'), default='—')}")
        cols[2].write(f"**Email:** {text(field(lead, 'email'), default='—')}")

        contact = text(field(lead, "contact_person"))
        if contact:
            st.caption(f"Contact: {contact}")
        address = " · ".join(
            part
            for part in (
                text(field(lead, "address_line1")),
                text(field(lead, "address_line2")),
                text(field(lead, "area")),
                text(field(lead, "city")),
                text(field(lead, "pincode")),
            )
            if part
        )
        if address:
            st.caption(f"Address: {address}")
        tax_bits = [
            f"GSTIN: {text(field(lead, 'gstin'))}" if field(lead, "gstin") else "",
            f"State: {text(field(lead, 'state_code'))}"
            if field(lead, "state_code")
            else "",
        ]
        tax_line = " · ".join(bit for bit in tax_bits if bit)
        if tax_line:
            st.caption(tax_line)
        products = text(field(lead, "interested_products"))
        if products:
            st.caption(f"Interested in: {products}")
        notes = text(field(lead, "notes"))
        if notes:
            st.caption(f"Notes: {notes}")


def _quick_actions(lead, lead_id: str) -> None:
    status = text(field(lead, "status"))
    converted = status == LeadStatus.CONVERTED.value
    lost = status == LeadStatus.LOST.value

    with st.container(border=True):
        st.markdown("**Quick Actions**")
        row1 = st.columns(4)
        if row1[0].button(":material/edit: Edit", key="crm_ld_edit", width="stretch"):
            dialogs.arm(dialogs.LEAD_EDIT, lead_id)
            st.rerun()
        if row1[1].button(
            ":material/person_add: Assign", key="crm_ld_assign", width="stretch"
        ):
            dialogs.arm(dialogs.LEAD_ASSIGN, lead_id)
            st.rerun()
        if row1[2].button(
            ":material/flag: Status",
            key="crm_ld_status",
            width="stretch",
            disabled=converted,
        ):
            dialogs.arm(dialogs.LEAD_STATUS, lead_id)
            st.rerun()
        if row1[3].button(
            ":material/event: Log Activity", key="crm_ld_activity", width="stretch"
        ):
            dialogs.arm(
                dialogs.ACTIVITY_ADD,
                {"lead_id": lead_id, "party_name": text(field(lead, "name"))},
            )
            st.rerun()

        row2 = st.columns(4)
        if row2[0].button(
            ":material/contact_mail: New Enquiry", key="crm_ld_enquiry", width="stretch"
        ):
            dialogs.arm(
                dialogs.ENQUIRY_ADD,
                {"lead_id": lead_id, "party_name": text(field(lead, "name"))},
            )
            st.rerun()
        if lost:
            if row2[1].button(
                ":material/restart_alt: Reopen", key="crm_ld_reopen", width="stretch"
            ):
                dialogs.arm(dialogs.LEAD_REOPEN, lead_id)
                st.rerun()
        else:
            if row2[1].button(
                ":material/block: Mark Lost",
                key="crm_ld_lost",
                width="stretch",
                disabled=converted,
            ):
                dialogs.arm(dialogs.LEAD_LOST, lead_id)
                st.rerun()
        if row2[2].button(
            ":material/how_to_reg: Convert",
            key="crm_ld_convert",
            width="stretch",
            type="primary" if not converted else "secondary",
            disabled=converted,
            help="Create or link a customer record for this lead",
        ):
            dialogs.arm(dialogs.LEAD_CONVERT, lead_id)
            st.rerun()
        customer_id = text(field(lead, "customer_id"))
        if row2[3].button(
            ":material/group: Open Customer",
            key="crm_ld_customer",
            width="stretch",
            disabled=not customer_id,
            help="Open the linked customer record"
            if customer_id
            else "This lead is not linked to a customer yet",
        ):
            navigation.go_to_detail("customer_detail", customer_id)


def _enquiries_section(adapter, lead_id: str) -> None:
    enquiries = adapter.enquiries_for(lead_id=lead_id)
    with st.container(border=True):
        st.subheader(f"Enquiries ({len(enquiries)})")
        if not enquiries:
            st.caption("No enquiries recorded for this lead.")
            return
        for enquiry in enquiries:
            row = st.columns([3, 2, 1], vertical_alignment="center")
            row[0].markdown(
                f"**{text(field(enquiry, 'enquiry_number'), default='Enquiry')}** · "
                f"{text(field(enquiry, 'product_interest'), default='—')}"
            )
            status = text(field(enquiry, "status"))
            row[1].markdown(
                status_badge(status, status_color(status), compact=True),
                unsafe_allow_html=True,
            )
            if row[2].button("View", key=f"crm_ld_enq_{record_id(enquiry)}"):
                navigation.go_to_detail("crm_enquiry_detail", record_id(enquiry))


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page(PAGE_KEY)
    mark_wired("nav.back")

    if st.button("← Back to leads", key="crm_lead_back") or consume_action("nav.back"):
        navigation.go_back_to_list("crm_leads", "crm_leads_list")
        return

    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    lead_id = navigation.current_detail_id(PAGE_KEY)
    lead = adapter.get_lead(lead_id) if lead_id else None
    if lead is None:
        st.error("Lead not found.")
        return

    with panel(f"crm_lead_{lead_id}"):
        _header(lead)
        _profile(lead)

    metric_grid(
        [
            ("Estimated Value", fmt_money(field(lead, "estimated_value"), "₹0")),
            ("Owner", owner_label(lead)),
            ("Next Follow-up", fmt_datetime(field(lead, "next_follow_up_at"))),
            ("Last Activity", fmt_datetime(field(lead, "last_activity_at"))),
        ],
        suffix=f"crm_lead_{lead_id}",
    )

    _quick_actions(lead, lead_id)
    _enquiries_section(adapter, lead_id)

    with st.container(border=True):
        st.subheader("Activity Timeline")
        render_timeline(
            adapter.timeline(lead_id=lead_id),
            empty_text="No activity recorded for this lead yet.",
        )

    dialogs.open_all_dialogs_if_armed(adapter, services)
