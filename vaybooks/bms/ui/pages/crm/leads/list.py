"""CRM leads list: search / filter / sort / paginate, bulk actions, export."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui import filtering as F
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.crm import dialogs
from vaybooks.bms.ui.components.crm.cards import lead_card
from vaybooks.bms.ui.components.crm.common import CRM_UNAVAILABLE_TEXT, page_adapter
from vaybooks.bms.ui.crm_adapters import record_id
from vaybooks.bms.ui.crm_list_schemas import CRM_LEADS
from vaybooks.bms.ui.pages.crm.export import (
    LEAD_EXPORT_COLUMNS,
    export_filename,
    records_to_csv,
)
from vaybooks.bms.ui.styles import render_card_grid

PAGE_KEY = "crm_leads_list"
SELECTION = "crm_lead_selection"
BULK_MODE = "crm_lead_bulk_mode"
_LOADED = "_crm_leads_loaded"


def _selection() -> list[str]:
    return list(st.session_state.get(SELECTION) or [])


def _toggle_selection(lead_id: str, selected: bool) -> None:
    current = _selection()
    if selected and lead_id not in current:
        current.append(lead_id)
    elif not selected and lead_id in current:
        current.remove(lead_id)
    st.session_state[SELECTION] = current


def _load_leads(services: dict, filters: dict, sort) -> list:
    adapter = page_adapter(services)
    rows = adapter.list_leads(limit=2000)
    st.session_state[_LOADED] = rows
    return rows


def _render_cards(page_leads, services: dict) -> None:
    bulk = bool(st.session_state.get(BULK_MODE))
    selected = set(_selection())

    def _render(lead, _index: int) -> None:
        lead_id = record_id(lead)
        edit_clicked = lead_card(
            lead,
            f"crm_lead_{lead_id}",
            selected=lead_id in selected,
            selectable=bulk,
            on_select=_toggle_selection,
        )
        if edit_clicked:
            dialogs.arm(dialogs.LEAD_EDIT, lead_id)
            st.rerun()

    render_card_grid(page_leads, _render, suffix="crm_leads")


def _toolbar(filtered: list) -> None:
    cols = st.columns([1.2, 1.2, 1.2, 1.4])
    bulk = bool(st.session_state.get(BULK_MODE))
    if cols[0].button(
        "Exit bulk mode" if bulk else "Bulk actions",
        key="crm_leads_bulk_toggle",
        width="stretch",
    ):
        st.session_state[BULK_MODE] = not bulk
        if bulk:
            st.session_state[SELECTION] = []
        st.rerun()

    with cols[1]:
        st.download_button(
            "Export CSV",
            data=records_to_csv(filtered, LEAD_EXPORT_COLUMNS),
            file_name=export_filename("crm_leads"),
            mime="text/csv",
            key="crm_leads_export",
            disabled=not filtered,
            width="stretch",
            icon=":material/download:",
            help="Downloads every lead matching the current filters.",
        )

    if cols[2].button(
        "Import leads",
        key="crm_leads_import",
        width="stretch",
        icon=":material/upload_file:",
        help="Opens the Data Migration wizard for leads.",
    ):
        navigation.go_to_list("data_migration", entity="leads")
        return

    selected = _selection()
    if bulk:
        with cols[3]:
            if st.button(
                f"Apply to {len(selected)} selected",
                key="crm_leads_bulk_apply",
                type="primary",
                width="stretch",
                disabled=not selected,
            ):
                dialogs.arm(dialogs.LEAD_BULK, selected)
                st.rerun()
        picker = st.columns([1.2, 1.2, 3])
        if picker[0].button(
            "Select page", key="crm_leads_select_page", width="stretch"
        ):
            page_ids = [record_id(r) for r in st.session_state.get("_crm_leads_page", [])]
            st.session_state[SELECTION] = sorted(set(selected) | set(page_ids))
            st.rerun()
        if picker[1].button("Clear selection", key="crm_leads_clear_sel", width="stretch"):
            st.session_state[SELECTION] = []
            st.rerun()


def render(services: dict) -> None:
    from vaybooks.bms.ui.keyboard.context import set_current_page
    from vaybooks.bms.ui.keyboard.wired import mark_wired

    set_current_page(PAGE_KEY)
    mark_wired("list.filters.open", "list.sort.open", "list.primary")

    adapter = page_adapter(services)
    if not adapter.available:
        st.markdown("### Leads")
        st.info(CRM_UNAVAILABLE_TEXT)
        return

    bar = render_list(
        CRM_LEADS,
        services=services,
        load_fn=_load_leads,
        card_renderer=_render_cards,
        primary_label="Add Lead",
        primary_key="crm_leads_add_btn",
        count_label="leads",
        empty_text="No leads match these filters.",
        page_key_nav=PAGE_KEY,
    )
    st.session_state["_crm_leads_page"] = bar.get("page_items") or []

    filtered = F.apply_filters(
        st.session_state.get(_LOADED) or [], CRM_LEADS, bar["filters"]
    )
    _toolbar(filtered)

    if bar["primary_clicked"]:
        dialogs.arm(dialogs.LEAD_ADD)
        st.rerun()
    if bar.get("view_nth"):
        navigation.go_to_detail("crm_lead_detail", bar["view_nth"])
    if bar.get("edit_nth"):
        dialogs.arm(dialogs.LEAD_EDIT, bar["edit_nth"])
        st.rerun()

    dialogs.open_lead_dialogs_if_armed(adapter, services)
