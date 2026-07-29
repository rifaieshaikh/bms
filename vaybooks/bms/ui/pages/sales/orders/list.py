"""Sales orders list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.sales.sales_order_card import _so_row, sales_order_cards
from vaybooks.bms.ui.components.sales.sales_order_dialog import arm_so_dialog, open_so_dialog_if_armed
from vaybooks.bms.ui.sales_list_schemas import SALES_ORDERS


def _load(services, filters, sort):
    try:
        from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
        from vaybooks.bms.ui.auth.session import working_location_list_context

        working, accessible = working_location_list_context(services)
        filt = location_id_mongo_filter(working, accessible)
        return [
            _so_row(so)
            for so in services["sales"].list_sales_orders(location_filter=filt)
        ]
    except Exception:
        return []


def render(services: dict) -> None:
    bar = render_list(
        SALES_ORDERS,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: sales_order_cards(rows, suffix="so_list"),
        primary_label="+ Create SO",
        primary_key="so_create_btn",
        title="Sales Orders",
        count_label="orders",
        empty_text="No sales orders yet.",
        page_key_nav="sales_orders_list",
    )
    if bar["primary_clicked"]:
        arm_so_dialog()
        st.rerun()
    open_so_dialog_if_armed(services)
