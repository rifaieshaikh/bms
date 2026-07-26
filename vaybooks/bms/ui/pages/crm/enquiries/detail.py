"""CRM enquiry detail route (`?id=<enquiry_id>`)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.crm.enums import EnquiryStatus
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
from vaybooks.bms.ui.crm_adapters import field, text
from vaybooks.bms.ui.styles import metric_grid, panel, status_badge

PAGE_KEY = "crm_enquiry_detail"

CLOSED_STATUSES = (
    EnquiryStatus.WON.value,
    EnquiryStatus.LOST.value,
    EnquiryStatus.CLOSED.value,
)


def _header(enquiry) -> None:
    title_col, badge_col = st.columns([3, 2], vertical_alignment="center")
    with title_col:
        st.title(text(field(enquiry, "party_name"), default="Enquiry"))
        st.caption(text(field(enquiry, "enquiry_number")))
    with badge_col:
        status = text(field(enquiry, "status"))
        priority = text(field(enquiry, "priority"))
        st.markdown(
            status_badge(status, status_color(status))
            + " "
            + status_badge(priority, priority_color(priority)),
            unsafe_allow_html=True,
        )
    if status == EnquiryStatus.LOST.value:
        st.error(
            f"Lost — {text(field(enquiry, 'lost_reason'), default='no reason recorded')}"
        )


def _profile(enquiry) -> None:
    with st.container(border=True):
        cols = st.columns(3)
        cols[0].write(
            f"**Product:** {text(field(enquiry, 'product_interest'), default='—')}"
        )
        cols[1].write(f"**Source:** {text(field(enquiry, 'source'), default='—')}")
        cols[2].write(
            f"**Quantity:** {text(field(enquiry, 'expected_quantity'), default='—')}"
        )
        description = text(field(enquiry, "description"))
        if description:
            st.caption(description)
        notes = text(field(enquiry, "notes"))
        if notes:
            st.caption(f"Notes: {notes}")
        links = []
        if text(field(enquiry, "quotation_id")):
            links.append("Quotation linked")
        if text(field(enquiry, "sales_order_id")):
            links.append("Sales order linked")
        if links:
            st.caption(" · ".join(links))


def _quick_actions(enquiry, enquiry_id: str, adapter) -> None:
    status = text(field(enquiry, "status"))
    closed = status in CLOSED_STATUSES
    party_name = text(field(enquiry, "party_name"))

    with st.container(border=True):
        st.markdown("**Quick Actions**")
        row = st.columns(5)
        if row[0].button(":material/edit: Edit", key="crm_ed_edit", width="stretch"):
            dialogs.arm(dialogs.ENQUIRY_EDIT, enquiry_id)
            st.rerun()
        if row[1].button(
            ":material/person_add: Assign", key="crm_ed_assign", width="stretch"
        ):
            dialogs.arm(dialogs.ENQUIRY_ASSIGN, enquiry_id)
            st.rerun()
        if row[2].button(":material/flag: Status", key="crm_ed_status", width="stretch"):
            dialogs.arm(dialogs.ENQUIRY_STATUS, enquiry_id)
            st.rerun()
        if row[3].button(
            ":material/event: Log Activity", key="crm_ed_activity", width="stretch"
        ):
            dialogs.arm(
                dialogs.ACTIVITY_ADD,
                {
                    "enquiry_id": enquiry_id,
                    "lead_id": text(field(enquiry, "lead_id")),
                    "customer_id": text(field(enquiry, "customer_id")),
                    "party_name": party_name,
                },
            )
            st.rerun()
        with row[4]:
            if closed:
                if st.button(
                    ":material/restart_alt: Reopen", key="crm_ed_reopen", width="stretch"
                ):
                    _run(lambda: adapter.reopen_enquiry(enquiry_id), "Enquiry reopened")
            else:
                if st.button(
                    ":material/task_alt: Close", key="crm_ed_close", width="stretch"
                ):
                    _run(lambda: adapter.close_enquiry(enquiry_id), "Enquiry closed")


def _run(action, success: str) -> None:
    try:
        action()
    except Exception as exc:  # noqa: BLE001 - surface backend errors to the user
        st.error(f"Could not complete the action: {exc}")
        return
    st.success(success)
    st.rerun()


def _party_links(enquiry) -> None:
    lead_id = text(field(enquiry, "lead_id"))
    customer_id = text(field(enquiry, "customer_id"))
    if not (lead_id or customer_id):
        return
    cols = st.columns(2)
    if lead_id and cols[0].button(
        ":material/person: Open Lead", key="crm_ed_open_lead", width="stretch"
    ):
        navigation.go_to_detail("crm_lead_detail", lead_id)
    if customer_id and cols[1].button(
        ":material/group: Open Customer", key="crm_ed_open_cust", width="stretch"
    ):
        navigation.go_to_detail("customer_detail", customer_id)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page(PAGE_KEY)
    mark_wired("nav.back")

    if st.button("← Back to enquiries", key="crm_enquiry_back") or consume_action(
        "nav.back"
    ):
        navigation.go_back_to_list("crm_enquiries", "crm_enquiries_list")
        return

    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    enquiry_id = navigation.current_detail_id(PAGE_KEY)
    enquiry = adapter.get_enquiry(enquiry_id) if enquiry_id else None
    if enquiry is None:
        st.error("Enquiry not found.")
        return

    with panel(f"crm_enquiry_{enquiry_id}"):
        _header(enquiry)
        _profile(enquiry)

    metric_grid(
        [
            ("Estimated Value", fmt_money(field(enquiry, "estimated_value"), "₹0")),
            ("Owner", owner_label(enquiry)),
            ("Expected Decision", fmt_datetime(field(enquiry, "expected_decision_at"))),
            ("Next Follow-up", fmt_datetime(field(enquiry, "next_follow_up_at"))),
        ],
        suffix=f"crm_enquiry_{enquiry_id}",
    )

    _quick_actions(enquiry, enquiry_id, adapter)
    _party_links(enquiry)

    with st.container(border=True):
        st.subheader("Activity Timeline")
        render_timeline(
            adapter.timeline(enquiry_id=enquiry_id),
            empty_text="No activity recorded for this enquiry yet.",
        )

    dialogs.open_enquiry_dialogs_if_armed(adapter, services)
    dialogs.open_activity_dialogs_if_armed(adapter, services)
