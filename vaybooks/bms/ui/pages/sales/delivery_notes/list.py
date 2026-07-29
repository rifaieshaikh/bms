"""Delivery notes list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.sales.delivery_note_card import _dn_row, delivery_note_cards
from vaybooks.bms.ui.components.sales.delivery_note_dialog import arm_dn_dialog, open_dn_dialog_if_armed
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.sales_list_schemas import DELIVERY_NOTES


def _load(services, filters, sort):
    try:
        from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
        from vaybooks.bms.ui.auth.session import working_location_list_context

        working, accessible = working_location_list_context(services)
        filt = location_id_mongo_filter(working, accessible)
        return [
            _dn_row(dn)
            for dn in services["sales"].list_delivery_notes(location_filter=filt)
        ]
    except Exception:
        return []


def render(services: dict) -> None:
    bar = render_list(
        DELIVERY_NOTES,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: delivery_note_cards(rows, suffix="dn_list"),
        primary_label="+ Create Delivery",
        primary_key="dn_create_btn",
        title="Delivery Notes",
        count_label="deliveries",
        empty_text="No delivery notes yet.",
        page_key_nav="delivery_notes_list",
    )
    if bar["primary_clicked"]:
        arm_dn_dialog()
        st.rerun()
    open_dn_dialog_if_armed(services)
