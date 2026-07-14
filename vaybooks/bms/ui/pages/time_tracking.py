import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui.components.filter_sort_bar import render_filter_sort_bar
from vaybooks.bms.ui.components.time_entry_card import time_entry_card
from vaybooks.bms.ui.components.time_entry_dialogs import (
    PENDING_EDIT_TIME_ENTRY,
    TIME_PAGE_RECORD_OPEN,
    edit_time_dialog,
    record_time_dialog,
)
from vaybooks.bms.ui.list_schemas import TIME
from vaybooks.bms.ui.styles import render_card_grid


def _render_entries(services: dict, time_service, entries):
    if not entries:
        st.info("No time entries match your filters.")
        return

    st.caption(f"{len(entries)} time entries match your filters.")

    def _render(entry, _i):
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

    render_card_grid(entries, _render, suffix="tt_entries")


def render(services: dict):
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page("time_list")
    mark_wired("list.primary", "time.add", "list.filters.open", "list.sort.open")
    time_service = services["time_tracking"]

    bar = render_filter_sort_bar(
        TIME,
        services=services,
        primary_label="+ Record Time",
        primary_key="time_record_btn",
        title="Time Log",
    )
    if bar["primary_clicked"]:
        st.session_state[TIME_PAGE_RECORD_OPEN] = True
        st.rerun()

    try:
        all_entries = time_service.list_all()
    except Exception:
        all_entries = []
    filtered = F.apply_filters(all_entries, TIME, bar["filters"])
    entries = F.sort_records(filtered, TIME, bar["sort"])

    _render_entries(services, time_service, entries)

    if st.session_state.get(TIME_PAGE_RECORD_OPEN):
        record_time_dialog(services)

    pending_edit = st.session_state.get(PENDING_EDIT_TIME_ENTRY)
    if pending_edit:
        edit_time_dialog(services, pending_edit)
