"""Card renderers for CRM leads, enquiries, and activities."""

from __future__ import annotations

from typing import Any, Callable, Optional

import streamlit as st

from vaybooks.bms.domain.crm.enums import ActivityStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.crm.common import (
    days_overdue,
    fmt_datetime,
    fmt_money,
    owner_label,
    priority_color,
    status_color,
)
from vaybooks.bms.ui.crm_adapters import field, record_id, text
from vaybooks.bms.ui.styles import status_badge


def _badges(*pairs: tuple[str, str]) -> str:
    return " ".join(
        status_badge(label, color, compact=True) for label, color in pairs if label
    )


def lead_card(
    lead: Any,
    key_prefix: str,
    *,
    selected: bool = False,
    selectable: bool = False,
    on_select: Optional[Callable[[str, bool], None]] = None,
) -> bool:
    """Render one lead card. Returns True when Edit was clicked."""
    lead_id = record_id(lead)
    with st.container(border=True):
        header = text(field(lead, "name"), default="Unnamed lead")
        st.markdown(f"### {header}")
        number = text(field(lead, "lead_number"))
        if number:
            st.caption(number)

        phone = text(field(lead, "phone"))
        if phone:
            st.write(f"\U0001f4de {phone}")
        place = " · ".join(
            p for p in (text(field(lead, "area")), text(field(lead, "city"))) if p
        )
        if place:
            st.caption(place)

        st.markdown(
            _badges(
                (text(field(lead, "status")), status_color(field(lead, "status"))),
                (text(field(lead, "priority")), priority_color(field(lead, "priority"))),
                (text(field(lead, "source")), "gray"),
            ),
            unsafe_allow_html=True,
        )

        value = fmt_money(field(lead, "estimated_value"))
        if value != "—":
            st.caption(f"Estimated value: {value}")
        st.caption(f"Owner: {owner_label(lead)}")

        follow_up = field(lead, "next_follow_up_at")
        overdue = days_overdue(follow_up)
        if follow_up is not None:
            label = f"Follow-up: {fmt_datetime(follow_up)}"
            if overdue:
                st.markdown(
                    status_badge(f"{label} · {overdue}d overdue", "red", compact=True),
                    unsafe_allow_html=True,
                )
            else:
                st.caption(label)

        if selectable and on_select is not None:
            checked = st.checkbox(
                "Select",
                value=selected,
                key=f"{key_prefix}_select",
            )
            if checked != selected:
                on_select(lead_id, checked)

        edit_col, view_col = st.columns(2)
        edit_clicked = edit_col.button("Edit", key=f"{key_prefix}_edit", width="stretch")
        if view_col.button(
            "View", key=f"{key_prefix}_view", type="primary", width="stretch"
        ):
            navigation.go_to_detail("crm_lead_detail", lead_id)
    return edit_clicked


def enquiry_card(enquiry: Any, key_prefix: str) -> bool:
    """Render one enquiry card. Returns True when Edit was clicked."""
    enquiry_id = record_id(enquiry)
    with st.container(border=True):
        st.markdown(f"### {text(field(enquiry, 'party_name'), default='Enquiry')}")
        number = text(field(enquiry, "enquiry_number"))
        if number:
            st.caption(number)

        product = text(field(enquiry, "product_interest"))
        if product:
            st.write(product)

        st.markdown(
            _badges(
                (text(field(enquiry, "status")), status_color(field(enquiry, "status"))),
                (
                    text(field(enquiry, "priority")),
                    priority_color(field(enquiry, "priority")),
                ),
                (text(field(enquiry, "source")), "gray"),
            ),
            unsafe_allow_html=True,
        )

        value = fmt_money(field(enquiry, "estimated_value"))
        if value != "—":
            st.caption(f"Estimated value: {value}")
        st.caption(f"Owner: {owner_label(enquiry)}")

        decision = field(enquiry, "expected_decision_at")
        if decision is not None:
            st.caption(f"Expected decision: {fmt_datetime(decision)}")

        edit_col, view_col = st.columns(2)
        edit_clicked = edit_col.button("Edit", key=f"{key_prefix}_edit", width="stretch")
        if view_col.button(
            "View", key=f"{key_prefix}_view", type="primary", width="stretch"
        ):
            navigation.go_to_detail("crm_enquiry_detail", enquiry_id)
    return edit_clicked


def activity_card(activity: Any, key_prefix: str) -> str:
    """Render one activity card. Returns the clicked action id, else ``""``."""
    activity_id = record_id(activity)
    status = text(field(activity, "status"))
    automatic = text(field(activity, "origin")) == "Automatic"
    action = ""

    with st.container(border=True):
        st.markdown(f"### {text(field(activity, 'activity_type'), default='Activity')}")
        party = text(field(activity, "party_name"))
        if party:
            st.caption(party)

        scheduled = field(activity, "scheduled_at") or field(activity, "activity_at")
        overdue = (
            days_overdue(scheduled)
            if status in (ActivityStatus.SCHEDULED.value, ActivityStatus.IN_PROGRESS.value)
            else 0
        )
        st.markdown(
            _badges(
                (status, status_color(status)),
                (
                    text(field(activity, "priority")),
                    priority_color(field(activity, "priority")),
                ),
                ("Automatic", "violet") if automatic else ("", ""),
                (f"{overdue}d overdue", "red") if overdue else ("", ""),
            ),
            unsafe_allow_html=True,
        )

        if scheduled is not None:
            st.caption(f"Scheduled: {fmt_datetime(scheduled)}")
        st.caption(f"Owner: {owner_label(activity)}")

        outcome = text(field(activity, "outcome"))
        if outcome:
            st.caption(f"Outcome: {outcome}")
        notes = text(field(activity, "notes"))
        if notes:
            st.caption(notes[:160])

        open_now = status in (
            ActivityStatus.SCHEDULED.value,
            ActivityStatus.IN_PROGRESS.value,
        )
        cols = st.columns(4)
        if cols[0].button(
            "Complete",
            key=f"{key_prefix}_complete",
            disabled=automatic or not open_now,
            width="stretch",
            help=(
                "Automatic activities are recorded by transactions"
                if automatic
                else "Record the outcome of this activity"
            ),
        ):
            action = "complete"
        if cols[1].button(
            "Reschedule",
            key=f"{key_prefix}_reschedule",
            disabled=not open_now,
            width="stretch",
        ):
            action = "reschedule"
        if cols[2].button(
            "Cancel",
            key=f"{key_prefix}_cancel",
            disabled=not open_now,
            width="stretch",
        ):
            action = "cancel"
        if cols[3].button(
            "View", key=f"{key_prefix}_view", type="primary", width="stretch"
        ):
            navigation.go_to_detail("crm_activity_detail", activity_id)
    return action
