from datetime import date

import streamlit as st

from vaybooks.bms.domain.parties.workers.entities import SOURCE_STORE
from vaybooks.bms.domain.shared.date_utils import (
    calculate_duration_minutes,
    minutes_to_hours,
)
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.auth.session import current_working_location_id
from vaybooks.bms.ui.components.common.filter_sort_bar import render_filter_sort_bar
from vaybooks.bms.ui.dialog_utils import dismiss_armed_dialogs
from vaybooks.bms.ui.list_schemas import STORE_TIME
from vaybooks.bms.ui.styles import render_card_grid, status_badge

PENDING_EDIT_STORE_TIME_ENTRY = "pending_edit_store_time_entry"
STORE_TIME_RECORD_OPEN = "store_time_record_open"


def _time_tracked_activities(services) -> list:
    activities = services["store_activities"].list_activities(active_only=True)
    return [a for a in activities if a.requires_time_tracking]


def _location_options(services) -> dict:
    """Active locations as ``{id: label}`` with a blank "no location" entry."""
    inventory = services.get("inventory")
    options = {"": "—"}
    if inventory is None:
        return options
    try:
        for loc in inventory.list_locations(active_only=True):
            options[loc.id] = f"{loc.code} — {loc.name}" if loc.code else loc.name
    except Exception:
        pass
    return options


def _store_time_form(services, key_prefix: str, entry=None) -> dict:
    activities = _time_tracked_activities(services)
    activity_map = {a.activity_name: a for a in activities}
    names = list(activity_map.keys())
    default_index = 0
    if entry is not None and entry.activity_name in names:
        default_index = names.index(entry.activity_name)
    activity_name = (
        st.selectbox(
            "Store Activity", names, index=default_index,
            key=f"store_time_act_{key_prefix}",
        )
        if names
        else None
    )
    activity = activity_map.get(activity_name) if activity_name else None
    activity_id = activity.id if activity else None

    workers = (
        services["workers"].list_workers_by_activity(activity_id, source=SOURCE_STORE)
        if activity_id
        else []
    )
    worker_map = {w.worker_name: w for w in workers}
    worker_options = list(worker_map.keys()) if workers else ["—"]
    default_worker_index = 0
    if entry is not None and entry.worker_name in worker_options:
        default_worker_index = worker_options.index(entry.worker_name)
    selected_worker = st.selectbox(
        "Employee",
        worker_options,
        index=default_worker_index,
        key=f"store_time_worker_{key_prefix}",
    )
    worker = worker_map.get(selected_worker)
    if not workers:
        st.caption("No active employees are assigned to this store activity.")

    work_date = st.date_input(
        "Work Date",
        value=entry.work_date if entry else date.today(),
        key=f"store_time_date_{key_prefix}",
    )
    cols = st.columns(2)
    start_time = cols[0].text_input(
        "Start (HH:MM)",
        value=entry.start_time if entry else "10:00",
        key=f"store_time_start_{key_prefix}",
    )
    end_time = cols[1].text_input(
        "End (HH:MM)",
        value=entry.end_time if entry else "13:00",
        key=f"store_time_end_{key_prefix}",
    )
    ends_next_day = st.checkbox(
        "Ends next day (overnight shift)",
        value=False,
        key=f"store_time_overnight_{key_prefix}",
    )

    loc_opts = _location_options(services)
    loc_ids = list(loc_opts.keys())
    default_loc = entry.location_id if entry else current_working_location_id(services)
    loc_index = loc_ids.index(default_loc) if default_loc in loc_ids else 0
    location_id = st.selectbox(
        "Location",
        loc_ids,
        index=loc_index,
        format_func=lambda lid: loc_opts.get(lid, lid),
        key=f"store_time_loc_{key_prefix}",
    )

    notes = st.text_area(
        "Notes", value=entry.notes if entry else "", key=f"store_time_notes_{key_prefix}"
    )

    duration_minutes = None
    if start_time and end_time:
        try:
            duration_minutes = calculate_duration_minutes(
                start_time, end_time, ends_next_day=ends_next_day
            )
            hourly_rate = 0.0
            if worker is not None:
                hourly_rate = float(
                    worker.default_hourly_rate
                    or (activity.default_hourly_expense if activity else 0.0)
                    or 0.0
                )
            labour_cost = round((duration_minutes / 60) * hourly_rate, 2)
            st.info(
                f"Duration: {duration_minutes} minutes "
                f"({duration_minutes / 60:.2f} hours) · "
                f"Estimated labour cost: ₹{labour_cost:,.2f}"
            )
        except Exception as exc:
            st.error(str(exc))

    return {
        "activity_id": activity_id,
        "worker_id": worker.id if worker else None,
        "work_date": work_date,
        "start_time": start_time,
        "end_time": end_time,
        "ends_next_day": ends_next_day,
        "location_id": location_id or "",
        "location_name": loc_opts.get(location_id, "") if location_id else "",
        "notes": notes,
        "duration_minutes": duration_minutes,
    }


def _validate_form(data) -> str:
    if not data["activity_id"]:
        return "Select a store activity"
    if not data["worker_id"]:
        return "Select an employee assigned to this store activity"
    if not (data["start_time"] or "").strip() or not (data["end_time"] or "").strip():
        return "Start and end time are required"
    if data["duration_minutes"] is None:
        return "End time must be greater than start time"
    return ""


@st.dialog("Record Business Task", on_dismiss=dismiss_armed_dialogs)
def record_store_time_dialog(services: dict):
    time_service = services["store_time_tracking"]
    data = _store_time_form(services, "page_new")
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", width="stretch"):
        error = _validate_form(data)
        if error:
            st.session_state[STORE_TIME_RECORD_OPEN] = True
            st.error(error)
        else:
            try:
                time_service.record_time_entry(
                    activity_id=data["activity_id"],
                    worker_id=data["worker_id"],
                    work_date=data["work_date"],
                    start_time=data["start_time"],
                    end_time=data["end_time"],
                    location_id=data["location_id"],
                    location_name=data["location_name"],
                    notes=data["notes"],
                    ends_next_day=data["ends_next_day"],
                )
                st.session_state.pop(STORE_TIME_RECORD_OPEN, None)
                st.rerun()
            except (ValidationError, Exception) as exc:
                st.session_state[STORE_TIME_RECORD_OPEN] = True
                st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(STORE_TIME_RECORD_OPEN, None)
        st.rerun()


@st.dialog("Edit Business Task", on_dismiss=dismiss_armed_dialogs)
def edit_store_time_dialog(services: dict, entry_id: str):
    time_service = services["store_time_tracking"]
    entry = time_service.get_entry(entry_id)
    if not entry:
        st.error("Business task not found")
        return

    data = _store_time_form(services, f"page_edit_{entry_id}", entry=entry)
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", width="stretch"):
        error = _validate_form(data)
        if error:
            st.session_state[PENDING_EDIT_STORE_TIME_ENTRY] = entry_id
            st.error(error)
        else:
            try:
                time_service.update_time_entry(
                    entry_id,
                    work_date=data["work_date"],
                    start_time=data["start_time"],
                    end_time=data["end_time"],
                    notes=data["notes"],
                    ends_next_day=data["ends_next_day"],
                    activity_id=data["activity_id"],
                    worker_id=data["worker_id"],
                    location_id=data["location_id"],
                    location_name=data["location_name"],
                )
                st.session_state.pop(PENDING_EDIT_STORE_TIME_ENTRY, None)
                st.rerun()
            except (ValidationError, Exception) as exc:
                st.session_state[PENDING_EDIT_STORE_TIME_ENTRY] = entry_id
                st.error(str(exc))
    if cols[1].button("Cancel", width="stretch"):
        st.session_state.pop(PENDING_EDIT_STORE_TIME_ENTRY, None)
        st.rerun()


def _store_time_card(entry, key_prefix: str) -> tuple[bool, bool, bool]:
    hours = minutes_to_hours(entry.duration_minutes)
    with st.container(border=True):
        st.markdown(f"**🏬 {entry.activity_name}**")
        badge_color = "green" if entry.is_completed else "gray"
        st.markdown(
            status_badge(f"{hours:.1f} hrs", "gold")
            + " "
            + status_badge(entry.status, badge_color),
            unsafe_allow_html=True,
        )
        st.caption(f"👤 {entry.worker_name or '—'}")
        st.write(f"📅 {entry.work_date}  ·  🕑 {entry.start_time}–{entry.end_time}")
        if entry.location_name:
            st.caption(f"📍 {entry.location_name}")
        st.caption(f"💰 Labour cost: ₹{entry.labour_cost:,.2f}")
        if entry.notes:
            st.caption(f"📝 {entry.notes}")

        complete_clicked = False
        if not entry.is_completed:
            complete_clicked = st.button(
                "Mark Completed",
                key=f"{key_prefix}_done_{entry.id}",
                type="primary",
                width="stretch",
            )

        cols = st.columns(2)
        edit_clicked = cols[0].button(
            "Edit",
            key=f"{key_prefix}_edit_{entry.id}",
            width="stretch",
        )
        delete_clicked = cols[1].button(
            "Delete",
            key=f"{key_prefix}_del_{entry.id}",
            width="stretch",
        )

    return edit_clicked, delete_clicked, complete_clicked


def _render_entries(time_service, entries):
    if not entries:
        st.info("No business tasks match your filters.")
        return

    st.caption(f"{len(entries)} business tasks match your filters.")

    def _render(entry, _i):
        edit_clicked, delete_clicked, complete_clicked = _store_time_card(
            entry, f"stt_{entry.id}"
        )
        if complete_clicked:
            try:
                time_service.complete_task(entry.id)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        if edit_clicked:
            st.session_state[PENDING_EDIT_STORE_TIME_ENTRY] = entry.id
            st.rerun()
        if delete_clicked:
            try:
                time_service.delete_time_entry(entry.id)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))

    render_card_grid(entries, _render, suffix="stt_entries")


def render(services: dict):
    time_service = services["store_time_tracking"]

    bar = render_filter_sort_bar(
        STORE_TIME,
        services=services,
        primary_label="+ Record Business Task",
        primary_key="store_time_record_btn",
        title="Business Tasks",
    )
    if bar["primary_clicked"]:
        st.session_state[STORE_TIME_RECORD_OPEN] = True
        st.rerun()

    try:
        all_entries = time_service.list_all()
    except Exception:
        all_entries = []
    filtered = F.apply_filters(all_entries, STORE_TIME, bar["filters"])
    entries = F.sort_records(filtered, STORE_TIME, bar["sort"])

    _render_entries(time_service, entries)

    if st.session_state.get(STORE_TIME_RECORD_OPEN):
        record_store_time_dialog(services)

    pending_edit = st.session_state.get(PENDING_EDIT_STORE_TIME_ENTRY)
    if pending_edit:
        edit_store_time_dialog(services, pending_edit)
