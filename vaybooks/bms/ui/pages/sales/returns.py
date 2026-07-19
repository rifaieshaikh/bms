"""Sales returns list."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import SalesReturnStatus
from vaybooks.bms.ui import navigation
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.sales_return_card import _return_row, sales_return_cards
from vaybooks.bms.ui.components.sales_return_dialog import (
    arm_sales_return_dialog,
    open_sales_return_dialog_if_armed,
)
from vaybooks.bms.ui.components.sales_return_edit_dialog import (
    arm_sales_return_edit_dialog,
    open_sales_return_edit_dialog_if_armed,
)
from vaybooks.bms.ui.sales_list_schemas import SALES_RETURNS


def _load(services, filters, sort):
    try:
        sales = services["sales"]
        rows = []
        for sales_return in sales.list_sales_returns():
            row = _return_row(sales_return)
            if (
                not row.get("source_invoice_number")
                and sales_return.source_invoice_id
            ):
                invoice = sales.get_sales_invoice(sales_return.source_invoice_id) or {}
                row["source_invoice_number"] = (
                    invoice.get("store_invoice_number")
                    or invoice.get("voucher_number")
                    or sales_return.source_invoice_id
                )
            rows.append(row)
        return rows
    except Exception:
        return []


def render(services: dict) -> None:
    bar = render_list(
        SALES_RETURNS,
        services=services,
        load_fn=_load,
        card_renderer=lambda rows, s: sales_return_cards(rows, suffix="sales_returns_list"),
        primary_label="+ Record Return",
        primary_key="sales_return_create_btn",
        title="Sales Returns",
        count_label="returns",
        empty_text="No sales returns yet.",
        page_key_nav="sales_returns_list",
    )
    if bar["primary_clicked"]:
        arm_sales_return_dialog()
        st.rerun()
    if bar["view_nth"]:
        navigation.go_to_detail("sales_return_detail", bar["view_nth"])
        return
    if bar["edit_nth"]:
        sales_return = services["sales"].get_sales_return(bar["edit_nth"])
        if sales_return and sales_return.status == SalesReturnStatus.PENDING:
            arm_sales_return_edit_dialog(sales_return.id)
            st.rerun()
        else:
            st.warning("Only pending returns can be edited.")
    open_sales_return_dialog_if_armed(services)
    open_sales_return_edit_dialog_if_armed(services)
