"""Purchase orders list."""

from __future__ import annotations

import logging

import streamlit as st

from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.purchases.purchase_order_card import (
    _po_row,
    purchase_order_cards,
)
from vaybooks.bms.ui.components.purchases.purchase_order_dialog import (
    arm_po_dialog,
    consume_po_create_success,
    open_po_dialog_if_armed,
)
from vaybooks.bms.ui.purchase_list_schemas import PURCHASE_ORDERS

logger = logging.getLogger(__name__)


def _load(services, filters, sort):
    try:
        return [
            _po_row(po) for po in services["purchases"].list_purchase_orders()
        ]
    except Exception:
        logger.exception("Failed to load purchase orders")
        st.error("Could not load purchase orders. Check system logs.")
        return []


def render(services: dict) -> None:
    consume_po_create_success()
    bar = render_list(
        PURCHASE_ORDERS,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: purchase_order_cards(rows, suffix="po_list"),
        primary_label="+ Create PO",
        primary_key="po_create_btn",
        title="Purchase Orders",
        count_label="orders",
        empty_text="No purchase orders yet.",
        page_key_nav="purchase_orders_list",
    )
    if bar["primary_clicked"]:
        arm_po_dialog()
        st.rerun()
    open_po_dialog_if_armed(services)
