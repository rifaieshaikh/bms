"""CRM activities list with create / complete / reschedule / cancel actions."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.crm import dialogs
from vaybooks.bms.ui.components.crm.cards import activity_card
from vaybooks.bms.ui.components.crm.common import CRM_UNAVAILABLE_TEXT, page_adapter
from vaybooks.bms.ui.crm_adapters import record_id
from vaybooks.bms.ui.crm_list_schemas import CRM_ACTIVITIES
from vaybooks.bms.ui.pages.crm.export import (
    ACTIVITY_EXPORT_COLUMNS,
    export_filename,
    records_to_csv,
)
from vaybooks.bms.ui.styles import render_card_grid

PAGE_KEY = "crm_activities_list"
_LOADED = "_crm_activities_loaded"

_ACTION_FLAGS = {
    "complete": dialogs.ACTIVITY_COMPLETE,
    "reschedule": dialogs.ACTIVITY_RESCHEDULE,
    "cancel": dialogs.ACTIVITY_CANCEL,
}


def _load_activities(services: dict, filters: dict, sort) -> list:
    from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
    from vaybooks.bms.ui.auth.session import working_location_list_context

    working, accessible = working_location_list_context(services)
    filt = location_id_mongo_filter(working, accessible)
    rows = page_adapter(services).list_activities(limit=2000, location_filter=filt)
    st.session_state[_LOADED] = rows
    return rows


def _render_cards(page_activities, services: dict) -> None:
    def _render(activity, _index: int) -> None:
        activity_id = record_id(activity)
        action = activity_card(activity, f"crm_act_{activity_id}")
        flag = _ACTION_FLAGS.get(action)
        if flag:
            dialogs.arm(flag, activity_id)
            st.rerun()

    render_card_grid(page_activities, _render, suffix="crm_activities")


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page(PAGE_KEY)
    mark_wired("list.filters.open", "list.sort.open", "list.primary")

    adapter = page_adapter(services)
    if not adapter.available:
        st.markdown("### Activities")
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    bar = render_list(
        CRM_ACTIVITIES,
        services=services,
        load_fn=_load_activities,
        card_renderer=_render_cards,
        primary_label="Add Activity",
        primary_key="crm_activities_add_btn",
        count_label="activities",
        empty_text="No activities match these filters.",
        page_key_nav=PAGE_KEY,
    )

    filtered = F.apply_filters(
        st.session_state.get(_LOADED) or [], CRM_ACTIVITIES, bar["filters"]
    )
    st.download_button(
        "Export CSV",
        data=records_to_csv(filtered, ACTIVITY_EXPORT_COLUMNS),
        file_name=export_filename("crm_activities"),
        mime="text/csv",
        key="crm_activities_export",
        disabled=not filtered,
        icon=":material/download:",
        help="Downloads every activity matching the current filters.",
    )

    if bar["primary_clicked"]:
        dialogs.arm(dialogs.ACTIVITY_ADD, {})
        st.rerun()
    if bar.get("view_nth"):
        navigation.go_to_detail("crm_activity_detail", bar["view_nth"])

    dialogs.open_activity_dialogs_if_armed(adapter, services)
