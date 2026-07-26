"""CRM calendar: month / week / day / agenda views of scheduled activities."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

from vaybooks.bms.domain.crm.enums import ActivityStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.crm import dialogs
from vaybooks.bms.ui.components.crm.common import (
    CRM_UNAVAILABLE_TEXT,
    fmt_datetime,
    owner_label,
    page_adapter,
    status_color,
)
from vaybooks.bms.ui.crm_adapters import field, record_id, text
from vaybooks.bms.ui.pages.crm.calendar.events import (
    OVERDUE_COLOR,
    STATUS_COLORS,
    activities_to_events,
)
from vaybooks.bms.ui.styles import status_badge

PAGE_KEY = "crm_calendar"
_SELECTED = "crm_calendar_selected"

VIEWS = {
    "Month": "dayGridMonth",
    "Week": "timeGridWeek",
    "Day": "timeGridDay",
    "Agenda": "listMonth",
}

CALENDAR_OPTIONS = {
    "editable": True,
    "selectable": True,
    "navLinks": True,
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay,listMonth",
    },
    "slotMinTime": "06:00:00",
    "slotMaxTime": "22:00:00",
    "scrollTime": "08:00:00",
    "height": 720,
    "nowIndicator": True,
    "dayMaxEvents": True,
}


def _legend() -> None:
    items = [
        (ActivityStatus.SCHEDULED.value, STATUS_COLORS[ActivityStatus.SCHEDULED.value]),
        (
            ActivityStatus.IN_PROGRESS.value,
            STATUS_COLORS[ActivityStatus.IN_PROGRESS.value],
        ),
        (ActivityStatus.COMPLETED.value, STATUS_COLORS[ActivityStatus.COMPLETED.value]),
        ("Overdue", OVERDUE_COLOR),
    ]
    legend = " · ".join(
        f'<span style="color:{color};font-weight:600;">{label}</span>'
        for label, color in items
    )
    st.markdown(f"Colors: {legend}", unsafe_allow_html=True)


def _owner_filter(adapter) -> str:
    owners = adapter.owners()
    if not owners:
        return ""
    ids = [""] + [oid for oid, _ in owners]
    labels = {"": "All representatives", **dict(owners)}
    return st.selectbox(
        "Representative",
        ids,
        format_func=lambda v: labels.get(v, v),
        key="crm_calendar_owner",
    )


def _detail(activity, adapter) -> None:
    st.markdown(f"### {text(field(activity, 'activity_type'), default='Activity')}")
    party = text(field(activity, "party_name"))
    if party:
        st.caption(party)
    st.markdown(
        status_badge(
            text(field(activity, "status")), status_color(field(activity, "status"))
        ),
        unsafe_allow_html=True,
    )
    st.write(f"**Scheduled:** {fmt_datetime(field(activity, 'scheduled_at'))}")
    st.write(f"**Owner:** {owner_label(activity)}")
    notes = text(field(activity, "notes"))
    if notes:
        st.caption(notes)

    activity_id = record_id(activity)
    open_now = text(field(activity, "status")) in (
        ActivityStatus.SCHEDULED.value,
        ActivityStatus.IN_PROGRESS.value,
    )
    cols = st.columns(4)
    if cols[0].button(
        "Complete", key="crm_cal_complete", width="stretch", disabled=not open_now
    ):
        dialogs.arm(dialogs.ACTIVITY_COMPLETE, activity_id)
        st.rerun()
    if cols[1].button(
        "Reschedule", key="crm_cal_reschedule", width="stretch", disabled=not open_now
    ):
        dialogs.arm(dialogs.ACTIVITY_RESCHEDULE, activity_id)
        st.rerun()
    if cols[2].button(
        "Cancel", key="crm_cal_cancel", width="stretch", disabled=not open_now
    ):
        dialogs.arm(dialogs.ACTIVITY_CANCEL, activity_id)
        st.rerun()
    if cols[3].button("Open", key="crm_cal_open", type="primary", width="stretch"):
        navigation.go_to_detail("crm_activity_detail", activity_id)


def _selected_id(state) -> str:
    if not isinstance(state, dict):
        return ""
    clicked = state.get("eventClick") or {}
    event = clicked.get("event") if isinstance(clicked, dict) else None
    if not isinstance(event, dict):
        return ""
    event_id = event.get("id")
    if not event_id:
        event_id = (event.get("extendedProps") or {}).get("activity_id")
    return str(event_id or "")


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page

    set_current_page(PAGE_KEY)
    st.markdown("### CRM Calendar")

    adapter = page_adapter(services)
    if not adapter.available:
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    controls = st.columns([2, 2, 1])
    with controls[0]:
        view_label = st.segmented_control(
            "View", list(VIEWS), default="Month", key="crm_calendar_view"
        )
    with controls[1]:
        owner_id = _owner_filter(adapter)
    with controls[2]:
        if st.button("Add Activity", type="primary", key="crm_calendar_add"):
            dialogs.arm(dialogs.ACTIVITY_ADD, {})
            st.rerun()

    activities = adapter.list_activities(limit=2000)
    if owner_id:
        activities = [
            a for a in activities if text(field(a, "assigned_user_id")) == owner_id
        ]
    events = activities_to_events(activities)
    by_id = {record_id(a): a for a in activities}

    _legend()

    try:
        from streamlit_calendar import calendar
    except ImportError:
        st.error(
            "streamlit-calendar is not installed. "
            "Run `pip install streamlit-calendar` and restart the app."
        )
        return

    if not events:
        st.info("No scheduled activities to show yet.")

    options = {
        **CALENDAR_OPTIONS,
        "initialView": VIEWS.get(view_label or "Month", "dayGridMonth"),
    }
    state = calendar(
        events=events,
        options=options,
        callbacks=["eventClick", "eventDrop"],
        custom_css="""
        .fc-event-title { font-weight: 600; }
        .fc-toolbar-title { font-size: 1.25rem; }
        """,
        key=f"crm_fullcalendar_{options['initialView']}",
    )
    dropped = (state or {}).get("eventDrop")
    if dropped:
        event = dropped.get("event") or {}
        activity_id = text(event.get("id"))
        start_raw = text(event.get("start"))
        signature = f"{activity_id}:{start_raw}"
        if (
            activity_id
            and start_raw
            and st.session_state.get("_crm_calendar_last_drop") != signature
        ):
            try:
                scheduled_at = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
                if scheduled_at.tzinfo is not None:
                    scheduled_at = scheduled_at.replace(tzinfo=None)
                adapter.reschedule_activity(
                    activity_id, scheduled_at, "Rescheduled on CRM calendar"
                )
                st.session_state["_crm_calendar_last_drop"] = signature
                st.toast("Activity rescheduled", icon="✅")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    clicked = _selected_id(state)
    if clicked:
        st.session_state[_SELECTED] = clicked

    selected = st.session_state.get(_SELECTED)
    with st.expander("Activity details", expanded=bool(selected)):
        activity = by_id.get(selected) if selected else None
        if activity is None:
            st.caption("Click an activity on the calendar to see details.")
        else:
            _detail(activity, adapter)

    dialogs.open_activity_dialogs_if_armed(adapter, services)
