"""Stock Transfers list — filterable by status/location; primary New Transfer."""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.inventory.stock_transfer_dialog import (
    arm_transfer_dialog,
    open_transfer_dialog_if_armed,
)
from vaybooks.bms.ui.inventory_list_schemas import INVENTORY_TRANSFERS
from vaybooks.bms.ui.keyboard.wired import mark_wired
from vaybooks.bms.ui.styles import render_card_grid, status_badge


def _fmt_date(value) -> str:
    if isinstance(value, (date, datetime)):
        return value.strftime("%d %b %Y")
    return str(value) if value else "—"


def _load_transfers(services, filters, sort):
    try:
        return services["inventory"].list_stock_transfers()
    except Exception:
        return []


def _render_cards(page_transfers, services):
    def _render(transfer, _i):
        with st.container(border=True):
            st.markdown(
                f'<p class="z-card-title">{transfer.transfer_number}</p>',
                unsafe_allow_html=True,
            )
            st.caption(f"{transfer.from_location_name} → {transfer.to_location_name}")
            st.markdown(status_badge(transfer.status.value), unsafe_allow_html=True)
            st.caption(
                f"{_fmt_date(transfer.transfer_date)} · {len(transfer.lines)} line(s)"
            )
            if st.button(
                "View", key=f"inv_transfer_view_{transfer.id}", width="stretch"
            ):
                navigation.go_to_detail("inventory_transfer_detail", transfer.id)

    render_card_grid(page_transfers, _render, suffix="inv_transfers", card_min_width=240)


def render(services: dict):
    mark_wired(
        "inventory.transfers.add",
        "list.primary",
        "list.filters.open",
        "list.sort.open",
    )
    bar = render_list(
        INVENTORY_TRANSFERS,
        services=services,
        load_fn=_load_transfers,
        card_renderer=_render_cards,
        primary_label="New Transfer",
        primary_key="inv_transfers_add_btn",
        title="Stock Transfers",
        count_label="transfers",
        empty_text="No stock transfers yet.",
        page_key_nav="inventory_transfers_list",
    )
    if bar["primary_clicked"]:
        arm_transfer_dialog()
        st.rerun()
    open_transfer_dialog_if_armed(services)
