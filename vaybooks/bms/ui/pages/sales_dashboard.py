"""Sales list: record sale + filterable store sales."""

from __future__ import annotations

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.sales_card import sales_cards
from vaybooks.bms.ui.components.sales_invoice_dialog import (
    arm_sales_record_dialog,
    open_sales_record_dialog_if_armed,
)
from vaybooks.bms.domain.accounting.sales_parsing import sales_row_from_voucher
from vaybooks.bms.ui.list_schemas import STORE_SALES


def _load_sales(services, filters, sort):
    try:
        accounting = services["accounting"]
        discount = accounting.get_discount_account()
        discount_id = discount.id if discount else None
        vouchers = accounting.list_vouchers_by_type(VoucherType.SALES_INVOICE)
        return [sales_row_from_voucher(v, discount_id) for v in vouchers]
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
        title="Sales",
        count_label="sales",
        empty_text="No sales recorded yet.",
    )
    if bar["primary_clicked"]:
        arm_sales_record_dialog()
        st.rerun()

    open_sales_record_dialog_if_armed(services)
