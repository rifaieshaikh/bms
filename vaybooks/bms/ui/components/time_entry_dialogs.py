from datetime import date

import streamlit as st

from vaybooks.bms.domain.shared.date_utils import calculate_duration_minutes
from vaybooks.bms.domain.shared.exceptions import ValidationError
from vaybooks.bms.ui.components.bill_selector import bill_selector
from vaybooks.bms.ui.components.order_selector import order_selector
from vaybooks.bms.ui.dialog_utils import dismiss_armed_dialogs

PENDING_EDIT_TIME_ENTRY = "pending_edit_time_entry"
TIME_PAGE_RECORD_OPEN = "time_page_record_open"
TIME_PAGE_FIELD_ERRORS = "time_page_field_errors"


def item_activities(order, item):
    return order.activities_for_item(item.item_id)


def time_form_fields(
    item_activities_list,
    key_prefix,
    entry=None,
    *,
    field_errors=None,
    include_overnight=False,
):
    field_errors = field_errors or {}
    activity_map = {a.activity_name: a.activity_id for a in item_activities_list}
    names = list(activity_map.keys())
    default_index = 0
    if entry is not None and entry.activity_name in names:
        default_index = names.index(entry.activity_name)
    activity_name = (
        st.selectbox(
            "Activity", names, index=default_index, key=f"time_act_{key_prefix}"
        )
        if names
        else None
    )
    work_date = st.date_input(
        "Work Date",
        value=entry.work_date if entry else date.today(),
        key=f"time_date_{key_prefix}",
    )
    cols = st.columns(2)
    start_time = cols[0].text_input(
        "Start (HH:MM)",
        value=entry.start_time if entry else "10:00",
        key=f"time_start_{key_prefix}",
    )
    if field_errors.get("start_time"):
        st.error(field_errors["start_time"])
    end_time = cols[1].text_input(
        "End (HH:MM)",
        value=entry.end_time if entry else "13:00",
        key=f"time_end_{key_prefix}",
    )
    if field_errors.get("end_time"):
        st.error(field_errors["end_time"])
    ends_next_day = False
    if include_overnight:
        ends_next_day = st.checkbox(
            "Ends next day (overnight shift)",
            value=False,
            key=f"time_overnight_{key_prefix}",
        )
    worker = st.text_input(
        "Worker Name",
        value=entry.worker_name if entry else "",
        key=f"time_worker_{key_prefix}",
    )
    notes = st.text_area(
        "Notes", value=entry.notes if entry else "", key=f"time_notes_{key_prefix}"
    )

    duration_minutes = None
    if start_time and end_time:
        try:
            duration_minutes = calculate_duration_minutes(
                start_time, end_time, ends_next_day=ends_next_day
            )
            st.info(
                f"Duration: {duration_minutes} minutes "
                f"({duration_minutes / 60:.2f} hours)"
            )
        except Exception as exc:
            st.error(str(exc))

    return {
        "activity_id": activity_map.get(activity_name) if activity_name else None,
        "activity_name": activity_name,
        "work_date": work_date,
        "start_time": start_time,
        "end_time": end_time,
        "worker_name": worker,
        "notes": notes,
        "ends_next_day": ends_next_day,
        "duration_minutes": duration_minutes,
    }


def save_time_entry(services, order, item, data, entry, flag_key=None):
    time_service = services["time_tracking"]
    if entry is not None:
        if not data["activity_id"]:
            st.error("Select an activity for this time entry")
            return False
        time_service.update_time_entry(
            entry.id,
            data["work_date"],
            data["start_time"],
            data["end_time"],
            data["worker_name"],
            data["notes"],
            activity_id=data["activity_id"],
            activity_name=data["activity_name"],
            ends_next_day=data.get("ends_next_day", False),
        )
    else:
        if not data["activity_id"]:
            st.error("Add an activity to this item before recording time")
            return False
        time_service.record_time_entry(
            order_id=order.id,
            bill_id=item.item_id,
            activity_id=data["activity_id"],
            work_date=data["work_date"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            worker_name=data["worker_name"],
            notes=data["notes"],
            ends_next_day=data.get("ends_next_day", False),
        )
    if flag_key:
        st.session_state.pop(flag_key, None)
    st.session_state.pop(TIME_PAGE_FIELD_ERRORS, None)
    return True


def _validate_time_form(data) -> dict:
    field_errors = {}
    start_time = (data["start_time"] or "").strip()
    end_time = (data["end_time"] or "").strip()
    if not start_time:
        field_errors["start_time"] = "start_time: This field is required"
    if not end_time:
        field_errors["end_time"] = "end_time: This field is required"
    return field_errors


@st.dialog("Record Time", on_dismiss=dismiss_armed_dialogs)
def record_time_dialog(services: dict):
    order_id = order_selector(services, "time_page_ord")
    if not order_id:
        st.caption("Search and select an order to record time.")
        return

    order = services["orders"].get_order_detail(order_id)
    if not order:
        st.error("Order not found")
        return

    bill_id = bill_selector(order, "time_page_bill")
    if not bill_id:
        return

    item = order.get_item_by_id(bill_id)
    if not item:
        st.error("Bill not found")
        return

    activities = item_activities(order, item)
    field_errors = st.session_state.get(TIME_PAGE_FIELD_ERRORS, {})
    data = time_form_fields(
        activities,
        "page_new",
        field_errors=field_errors,
        include_overnight=True,
    )
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        field_errors = _validate_time_form(data)
        if field_errors:
            st.session_state[TIME_PAGE_RECORD_OPEN] = True
            st.session_state[TIME_PAGE_FIELD_ERRORS] = field_errors
            st.rerun()
        elif data["duration_minutes"] is None:
            st.session_state[TIME_PAGE_RECORD_OPEN] = True
            st.session_state.pop(TIME_PAGE_FIELD_ERRORS, None)
            st.error("End time must be greater than start time")
        else:
            st.session_state.pop(TIME_PAGE_RECORD_OPEN, None)
            st.session_state.pop(TIME_PAGE_FIELD_ERRORS, None)
            try:
                if save_time_entry(services, order, item, data, None):
                    st.rerun()
            except ValidationError as exc:
                st.session_state[TIME_PAGE_RECORD_OPEN] = True
                st.error(str(exc))
            except Exception as exc:
                st.session_state[TIME_PAGE_RECORD_OPEN] = True
                st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(TIME_PAGE_RECORD_OPEN, None)
        st.session_state.pop(TIME_PAGE_FIELD_ERRORS, None)
        st.rerun()


@st.dialog("Edit Time Entry", on_dismiss=dismiss_armed_dialogs)
def edit_time_dialog(services: dict, entry_id: str):
    time_service = services["time_tracking"]
    entry = time_service.get_entry(entry_id)
    if not entry:
        st.error("Time entry not found")
        return

    order = services["orders"].get_order_detail(entry.order_id)
    item = order.get_item_by_id(entry.bill_id) if order else None
    if not order or not item:
        st.error("Order or bill not found")
        return

    activities = item_activities(order, item)
    field_errors = st.session_state.get(TIME_PAGE_FIELD_ERRORS, {})
    data = time_form_fields(
        activities,
        f"page_edit_{entry_id}",
        entry=entry,
        field_errors=field_errors,
        include_overnight=True,
    )
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        field_errors = _validate_time_form(data)
        if field_errors:
            st.session_state[PENDING_EDIT_TIME_ENTRY] = entry_id
            st.session_state[TIME_PAGE_FIELD_ERRORS] = field_errors
            st.rerun()
        elif data["duration_minutes"] is None:
            st.session_state[PENDING_EDIT_TIME_ENTRY] = entry_id
            st.session_state.pop(TIME_PAGE_FIELD_ERRORS, None)
            st.error("End time must be greater than start time")
        else:
            st.session_state.pop(PENDING_EDIT_TIME_ENTRY, None)
            st.session_state.pop(TIME_PAGE_FIELD_ERRORS, None)
            try:
                if save_time_entry(services, order, item, data, entry):
                    st.rerun()
            except ValidationError as exc:
                st.session_state[PENDING_EDIT_TIME_ENTRY] = entry_id
                st.error(str(exc))
            except Exception as exc:
                st.session_state[PENDING_EDIT_TIME_ENTRY] = entry_id
                st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(PENDING_EDIT_TIME_ENTRY, None)
        st.session_state.pop(TIME_PAGE_FIELD_ERRORS, None)
        st.rerun()


@st.dialog("Record Time", on_dismiss=dismiss_armed_dialogs)
def item_time_dialog(services, order_id, item_id, key_prefix, flag_key):
    target = st.session_state.get(flag_key)
    order = services["orders"].get_order_detail(order_id)
    item = order.get_item_by_id(item_id) if order else None
    if not item:
        st.error("Item not found")
        return
    entry = None if target in (None, "new") else services["time_tracking"].get_entry(target)
    data = time_form_fields(item_activities(order, item), f"dlg_{key_prefix}", entry)
    cols = st.columns(2)
    if cols[0].button("Save", type="primary", use_container_width=True):
        try:
            if save_time_entry(services, order, item, data, entry, flag_key):
                st.rerun()
        except Exception as exc:
            st.error(str(exc))
    if cols[1].button("Cancel", use_container_width=True):
        st.session_state.pop(flag_key, None)
        st.rerun()
