from datetime import date

import streamlit as st

from vaybooks.bms.domain.boutique.time_tracking.entities import TaskType
from vaybooks.bms.ui.pages.boutique.calendar.events import (
    TYPE_COLORS,
    TYPE_LABELS,
    activity_color,
    entries_to_calendar_events,
    visible_range_around,
)

_SELECTED_ENTRY = "boutique_cal_selected_entry"


def _in_house_activity_names(services: dict) -> list[str]:
    try:
        activities = services["activities"].list_activities(active_only=True)
    except Exception:
        return []
    names = {
        a.activity_name
        for a in activities
        if getattr(a, "is_in_house", False)
        or getattr(a, "requires_time_tracking", False)
    }
    return sorted(names)


def _render_detail(entry_id: str, entries_by_id: dict):
    entry = entries_by_id.get(entry_id)
    if not entry:
        st.info("Select a task on the calendar to see details.")
        return
    type_label = TYPE_LABELS.get(entry.task_type, entry.task_type.value)
    st.markdown(f"### {entry.activity_name or type_label}")
    st.write(f"**Type:** {type_label}")
    st.write(f"**Order:** {entry.order_number}")
    if entry.bill_number:
        st.write(f"**Bill:** {entry.bill_number}")
    st.write(f"**Date:** {entry.work_date}")
    if entry.task_type == TaskType.ACTIVITY and entry.start_time and entry.end_time:
        st.write(f"**Time:** {entry.start_time} – {entry.end_time}")
        if entry.duration_minutes:
            st.write(f"**Duration:** {entry.duration_minutes} min")
    else:
        st.write("**Time:** All day")
    st.write(f"**Employee:** {entry.worker_name or '—'}")
    if entry.notes:
        st.caption(entry.notes)


def render(services: dict):
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("calendar_list")
    mark_wired("list.filters.open")

    st.markdown("### Calendar")

    activity_names = _in_house_activity_names(services)
    task_type_options: list[tuple[str, tuple[str, str | None]]] = [
        ("ETD", (TaskType.ETD.value, None)),
        ("Delivery", (TaskType.DELIVERY.value, None)),
    ]
    for name in activity_names:
        task_type_options.append((name, (TaskType.ACTIVITY.value, name)))
    task_type_options.append(("All Activities", (TaskType.ACTIVITY.value, None)))
    task_type_options.append(("All", ("all", None)))

    type_labels = [label for label, _ in task_type_options]
    type_values = {label: value for label, value in task_type_options}

    filter_cols = st.columns([2, 2])
    selected_type_label = filter_cols[0].selectbox(
        "Task Type",
        type_labels,
        index=0,
        key="cal_task_type",
    )
    task_type_filter, activity_filter = type_values[selected_type_label]

    workers = []
    try:
        workers = services["workers"].list_workers(active_only=True)
    except Exception:
        workers = []
    employee_options = ["All"] + sorted(
        {w.worker_name for w in workers if getattr(w, "worker_name", None)}
    )
    selected_employee = filter_cols[1].selectbox(
        "Employee",
        employee_options,
        index=0,
        key="cal_employee",
    )
    worker_filter = None if selected_employee == "All" else selected_employee

    start_date, end_date = visible_range_around(date.today())
    time_service = services["time_tracking"]
    entries = time_service.list_for_calendar(
        start_date,
        end_date,
        task_type=task_type_filter,
        worker_name=worker_filter,
        activity_name=activity_filter,
    )
    entries_by_id = {e.id: e for e in entries}
    events = entries_to_calendar_events(entries)

    legend_items = [
        ("ETD", TYPE_COLORS[TaskType.ETD]),
        ("Delivery", TYPE_COLORS[TaskType.DELIVERY]),
    ]
    legend_items.extend((name, activity_color(name)) for name in activity_names)
    legend = " · ".join(
        f'<span style="color:{color};font-weight:600;">{label}</span>'
        for label, color in legend_items
    )
    st.markdown(f"Colors: {legend}", unsafe_allow_html=True)

    calendar_options = {
        "editable": False,
        "selectable": False,
        "navLinks": True,
        "initialView": "timeGridWeek",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay",
        },
        "slotMinTime": "00:00:00",
        "slotMaxTime": "24:00:00",
        "scrollTime": "08:00:00",
        "height": 700,
        "nowIndicator": True,
        "dayMaxEvents": True,
    }

    try:
        from streamlit_calendar import calendar
    except ImportError:
        st.error(
            "streamlit-calendar is not installed. "
            "Run `pip install streamlit-calendar` and restart the app."
        )
        return

    state = calendar(
        events=events,
        options=calendar_options,
        callbacks=["eventClick"],
        custom_css="""
        .fc-event-title { font-weight: 600; }
        .fc-toolbar-title { font-size: 1.25rem; }
        """,
        key="boutique_fullcalendar",
    )

    if state and isinstance(state, dict):
        clicked = state.get("eventClick") or {}
        event = clicked.get("event") if isinstance(clicked, dict) else None
        if isinstance(event, dict):
            event_id = event.get("id")
            if not event_id:
                props = event.get("extendedProps") or {}
                event_id = props.get("entry_id")
            if event_id:
                st.session_state[_SELECTED_ENTRY] = event_id

    selected_id = st.session_state.get(_SELECTED_ENTRY)
    with st.expander("Task details", expanded=bool(selected_id)):
        if selected_id:
            _render_detail(selected_id, entries_by_id)
        else:
            st.caption("Click a task on the calendar to see details.")
