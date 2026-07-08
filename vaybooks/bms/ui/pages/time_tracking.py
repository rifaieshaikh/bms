from dataclasses import dataclass

import streamlit as st

from vaybooks.bms.application.report_filters import DateRange
from vaybooks.bms.domain.shared.date_utils import minutes_to_hours
from vaybooks.bms.ui.components.report_filters import render_date_range, render_quick_period
from vaybooks.bms.ui.components.time_entry_card import time_entry_card
from vaybooks.bms.ui.components.time_entry_dialogs import (
    PENDING_EDIT_TIME_ENTRY,
    TIME_PAGE_RECORD_OPEN,
    edit_time_dialog,
    record_time_dialog,
)


@dataclass
class TimeTrackingFilters:
    date_range: DateRange
    bill_number: str
    order_number: str
    worker_name: str
    activity_name: str


def _render_summary(time_service, entries) -> None:
    summary = time_service.get_summary_for_entries(entries)
    st.subheader("Totals")
    cols = st.columns(2)
    cols[0].metric("Total Stitching", f"{summary['total_stitching_hours']} hours")
    cols[1].metric("Total Hand Work", f"{summary['total_hand_work_hours']} hours")

    if summary["by_bill"]:
        st.markdown("**By Bill Number**")
        per_row = 3
        bill_items = list(summary["by_bill"].items())
        for start in range(0, len(bill_items), per_row):
            row = bill_items[start : start + per_row]
            cols = st.columns(per_row)
            for col, (bill, mins) in zip(cols, row):
                with col:
                    with st.container(border=True):
                        st.caption(bill)
                        st.markdown(f"**{mins / 60:.2f} hours**")

    if summary["by_activity"]:
        st.markdown("**By Activity**")
        per_row = 3
        act_items = list(summary["by_activity"].items())
        for start in range(0, len(act_items), per_row):
            row = act_items[start : start + per_row]
            cols = st.columns(per_row)
            for col, (act, mins) in zip(cols, row):
                with col:
                    with st.container(border=True):
                        st.caption(act)
                        st.markdown(f"**{minutes_to_hours(mins):.1f} hrs**")


def _render_filters(services: dict) -> TimeTrackingFilters:
    render_quick_period("tt_page")
    date_range = render_date_range("tt_page")
    st.caption(
        f"Work date {date_range.start:%d %b %Y} → {date_range.end:%d %b %Y}"
    )

    filter_cols = st.columns(4)
    bill_number = filter_cols[0].text_input(
        "Bill Number",
        key="tt_bill_filter",
        placeholder="Search bill #...",
    )
    order_number = filter_cols[1].text_input(
        "Order Number",
        key="tt_order_filter",
        placeholder="Search order #...",
    )
    worker_name = filter_cols[2].text_input(
        "Worker",
        key="tt_worker_filter",
        placeholder="Search worker...",
    )

    activities = services["activities"].list_activities(active_only=True)
    activity_options = ["All"] + sorted(a.activity_name for a in activities)
    activity_choice = filter_cols[3].selectbox(
        "Activity",
        activity_options,
        key="tt_activity_filter",
    )

    return TimeTrackingFilters(
        date_range=date_range,
        bill_number=bill_number,
        order_number=order_number,
        worker_name=worker_name,
        activity_name="" if activity_choice == "All" else activity_choice,
    )


def _has_active_filters(filters: TimeTrackingFilters) -> bool:
    return any(
        value.strip()
        for value in (
            filters.bill_number,
            filters.order_number,
            filters.worker_name,
            filters.activity_name,
        )
    )


def _search_entries(time_service, filters: TimeTrackingFilters):
    return time_service.search_entries(
        bill_number=filters.bill_number,
        order_number=filters.order_number,
        worker_name=filters.worker_name,
        activity_name=filters.activity_name,
        work_date_from=filters.date_range.start,
        work_date_to=filters.date_range.end,
    )


def _render_entries_tab(services: dict, time_service, entries, filters: TimeTrackingFilters):
    header_cols = st.columns([4, 1])
    with header_cols[1]:
        if st.button("+ Record Time", type="primary", use_container_width=True):
            st.session_state[TIME_PAGE_RECORD_OPEN] = True
            st.rerun()

    if not entries:
        if _has_active_filters(filters):
            st.info("No time entries match your filters.")
        else:
            st.info("No time entries in this period.")
        return

    st.caption(f"{len(entries)} time entries match your filters.")
    per_row = 2
    for start in range(0, len(entries), per_row):
        row = entries[start : start + per_row]
        cols = st.columns(per_row)
        for col, entry in zip(cols, row):
            with col:
                edit_clicked, delete_clicked = time_entry_card(entry, f"tt_{entry.id}")
                if edit_clicked:
                    st.session_state[PENDING_EDIT_TIME_ENTRY] = entry.id
                    st.rerun()
                if delete_clicked:
                    try:
                        time_service.delete_time_entry(entry.id)
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


def _render_dashboard_tab(time_service, entries, filters: TimeTrackingFilters):
    if not entries:
        if _has_active_filters(filters):
            st.info("No time entries match your filters.")
        else:
            st.info("No time entries in this period.")
        return

    st.caption(f"Summary for {len(entries)} time entries in the selected period.")
    _render_summary(time_service, entries)


def render(services: dict):
    st.title("Time Tracking")
    st.caption(
        "Record and review time logged against bills and activities. "
        "Filter by work date, bill, order, worker, or activity."
    )
    time_service = services["time_tracking"]
    filters = _render_filters(services)
    entries = _search_entries(time_service, filters)

    entries_tab, dashboard_tab = st.tabs(["Entries", "Dashboard"])

    with entries_tab:
        _render_entries_tab(services, time_service, entries, filters)

    with dashboard_tab:
        _render_dashboard_tab(time_service, entries, filters)

    if st.session_state.get(TIME_PAGE_RECORD_OPEN):
        record_time_dialog(services)

    pending_edit = st.session_state.get(PENDING_EDIT_TIME_ENTRY)
    if pending_edit:
        edit_time_dialog(services, pending_edit)
