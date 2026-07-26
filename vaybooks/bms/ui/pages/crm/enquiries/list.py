"""CRM enquiries list: search / filter / sort / paginate and export."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.crm import dialogs
from vaybooks.bms.ui.components.crm.cards import enquiry_card
from vaybooks.bms.ui.components.crm.common import CRM_UNAVAILABLE_TEXT, page_adapter
from vaybooks.bms.ui.crm_adapters import record_id
from vaybooks.bms.ui.crm_list_schemas import CRM_ENQUIRIES
from vaybooks.bms.ui.pages.crm.export import (
    ENQUIRY_EXPORT_COLUMNS,
    export_filename,
    records_to_csv,
)
from vaybooks.bms.ui.styles import render_card_grid

PAGE_KEY = "crm_enquiries_list"
_LOADED = "_crm_enquiries_loaded"


def _load_enquiries(services: dict, filters: dict, sort) -> list:
    rows = page_adapter(services).list_enquiries(limit=2000)
    st.session_state[_LOADED] = rows
    return rows


def _render_cards(page_enquiries, services: dict) -> None:
    def _render(enquiry, _index: int) -> None:
        enquiry_id = record_id(enquiry)
        if enquiry_card(enquiry, f"crm_enq_{enquiry_id}"):
            dialogs.arm(dialogs.ENQUIRY_EDIT, enquiry_id)
            st.rerun()

    render_card_grid(page_enquiries, _render, suffix="crm_enquiries")


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page(PAGE_KEY)
    mark_wired("list.filters.open", "list.sort.open", "list.primary")

    adapter = page_adapter(services)
    if not adapter.available:
        st.markdown("### Enquiries")
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    bar = render_list(
        CRM_ENQUIRIES,
        services=services,
        load_fn=_load_enquiries,
        card_renderer=_render_cards,
        primary_label="Add Enquiry",
        primary_key="crm_enquiries_add_btn",
        count_label="enquiries",
        empty_text="No enquiries match these filters.",
        page_key_nav=PAGE_KEY,
    )

    filtered = F.apply_filters(
        st.session_state.get(_LOADED) or [], CRM_ENQUIRIES, bar["filters"]
    )
    st.download_button(
        "Export CSV",
        data=records_to_csv(filtered, ENQUIRY_EXPORT_COLUMNS),
        file_name=export_filename("crm_enquiries"),
        mime="text/csv",
        key="crm_enquiries_export",
        disabled=not filtered,
        icon=":material/download:",
        help="Downloads every enquiry matching the current filters.",
    )

    if bar["primary_clicked"]:
        dialogs.arm(dialogs.ENQUIRY_ADD, {})
        st.rerun()
    if bar.get("view_nth"):
        navigation.go_to_detail("crm_enquiry_detail", bar["view_nth"])
    if bar.get("edit_nth"):
        dialogs.arm(dialogs.ENQUIRY_EDIT, bar["edit_nth"])
        st.rerun()

    dialogs.open_enquiry_dialogs_if_armed(adapter, services)
