"""Sales invoices list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.sales_card import sales_cards
from vaybooks.bms.ui.components.sales_invoice_dialog import (
    arm_sales_record_dialog,
    open_sales_record_dialog_if_armed,
)
from vaybooks.bms.ui.sales_list_schemas import STORE_SALES


def _load_sales(services, filters, sort):
    try:
        return services["sales"].list_sales_invoices()
    except Exception:
        return []


def _sales_cards(page_rows, services):
    sales_cards(page_rows, suffix="store_sales")


def render(services: dict) -> None:
    bar = render_list(
        STORE_SALES,
        services=services,
        load_fn=_load_sales,
        card_renderer=_sales_cards,
        primary_label="+ Record Sale",
        primary_key="store_sales_create_btn",
        title="Sales Invoices",
        count_label="invoices",
        empty_text="No sales invoices yet.",
    )
    if bar["primary_clicked"]:
        arm_sales_record_dialog()
        st.rerun()

    open_sales_record_dialog_if_armed(services)
