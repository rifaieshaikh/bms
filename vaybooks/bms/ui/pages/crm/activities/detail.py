"""CRM activity detail route (`?id=<activity_id>`)."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.crm.enums import ActivityStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.crm import dialogs
from vaybooks.bms.ui.components.crm.whatsapp import (
    arm_reminder_dialog,
    open_reminder_dialog_if_armed,
)
from vaybooks.bms.ui.components.crm.common import (
    CRM_UNAVAILABLE_TEXT,
    fmt_datetime,
    owner_label,
    page_adapter,
    priority_color,
    status_color,
)
from vaybooks.bms.ui.crm_adapters import field, text
from vaybooks.bms.ui.styles import metric_grid, panel, status_badge

PAGE_KEY = "crm_activity_detail"


def _header(activity) -> None:
    title_col, badge_col = st.columns([3, 2], vertical_alignment="center")
    with title_col:
        st.title(text(field(activity, "subject"), default="Activity"))
        st.caption(text(field(activity, "activity_type"), default="Activity"))
    with badge_col:
        status = text(field(activity, "status"))
        priority = text(field(activity, "priority"))
        st.markdown(
            status_badge(status, status_color(status))
            + " "
            + status_badge(priority, priority_color(priority)),
            unsafe_allow_html=True,
        )


def _related_links(activity) -> None:
    targets = [
        ("Lead", "crm_lead_detail", text(field(activity, "lead_id"))),
        ("Enquiry", "crm_enquiry_detail", text(field(activity, "enquiry_id"))),
        ("Customer", "customer_detail", text(field(activity, "customer_id"))),
    ]
    targets = [item for item in targets if item[2]]
    if not targets:
        return
    cols = st.columns(len(targets))
    for col, (label, route, record) in zip(cols, targets):
        if col.button(
            f":material/open_in_new: Open {label}",
            key=f"crm_ad_open_{route}",
            width="stretch",
        ):
            navigation.go_to_detail(route, record)


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.actions import consume_action
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page(PAGE_KEY)
    mark_wired("nav.back")

    if st.button("← Back to activities", key="crm_activity_back") or consume_action(
        "nav.back"
    ):
        navigation.go_back_to_list("crm_activities", "crm_activities_list")
        return

    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    activity_id = navigation.current_detail_id(PAGE_KEY)
    activity = adapter.get_activity(activity_id) if activity_id else None
    if activity is None:
        st.error("Activity not found.")
        return

    with panel(f"crm_activity_{activity_id}"):
        _header(activity)
        description = text(field(activity, "description"))
        if description:
            st.write(description)
        outcome = text(field(activity, "outcome"))
        if outcome:
            st.success(f"Outcome: {outcome}")

    metric_grid(
        [
            ("Scheduled", fmt_datetime(field(activity, "scheduled_at"))),
            ("Next Follow-up", fmt_datetime(field(activity, "next_follow_up_at"))),
            ("Completed", fmt_datetime(field(activity, "completed_at"))),
            ("Owner", owner_label(activity)),
        ],
        suffix=f"crm_activity_{activity_id}",
    )

    open_status = text(field(activity, "status")) not in (
        ActivityStatus.COMPLETED.value,
        ActivityStatus.CANCELLED.value,
    )
    with st.container(border=True):
        st.markdown("**Quick Actions**")
        customer_id = text(field(activity, "customer_id"))
        row = st.columns(4 if customer_id else 3)
        if row[0].button(
            ":material/check_circle: Complete",
            key="crm_ad_complete",
            width="stretch",
            disabled=not open_status,
        ):
            dialogs.arm(dialogs.ACTIVITY_COMPLETE, activity_id)
            st.rerun()
        if row[1].button(
            ":material/event_repeat: Reschedule",
            key="crm_ad_reschedule",
            width="stretch",
            disabled=not open_status,
        ):
            dialogs.arm(dialogs.ACTIVITY_RESCHEDULE, activity_id)
            st.rerun()
        if row[2].button(
            ":material/cancel: Cancel",
            key="crm_ad_cancel",
            width="stretch",
            disabled=not open_status,
        ):
            dialogs.arm(dialogs.ACTIVITY_CANCEL, activity_id)
            st.rerun()
        if customer_id and row[3].button(
            ":material/chat: WhatsApp reminder",
            key="crm_ad_whatsapp",
            width="stretch",
        ):
            arm_reminder_dialog(customer_id)
            st.rerun()

    _related_links(activity)

    dialogs.open_activity_dialogs_if_armed(adapter, services)
    open_reminder_dialog_if_armed(services, adapter)
