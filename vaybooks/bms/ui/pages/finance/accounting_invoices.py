"""Accounting Invoices route (customization + sales invoices)."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.list_schemas import ACCOUNTING_INVOICES
from vaybooks.bms.ui.pages import accounts as acc
from vaybooks.bms.ui.styles import render_card_grid


def _load(services, filters, sort):
    try:
        accounting = services["accounting"]
        customization = accounting.list_vouchers_by_type(
            VoucherType.CUSTOMIZATION_INVOICE
        )
        sales = accounting.list_vouchers_by_type(VoucherType.SALES_INVOICE)
        return customization + sales
    except Exception:
        return []


def _cards(page_vouchers, services):
    def _render(v, _i):
        gross = acc._invoice_gross_amount(v)
        customer_name = v.lines[0].account_name if v.lines else "—"
        is_customization = v.voucher_type == VoucherType.CUSTOMIZATION_INVOICE
        tag = "Customization" if is_customization else "Sales"
        flag_key = acc.INV_CUST if is_customization else acc.INV_SALES
        edit_prefix = "edit_cust_inv" if is_customization else "edit_sales_inv"
        order_ref = " · Order linked" if v.reference_order_id else ""
        with st.container(border=True):
            st.markdown(f"**{v.voucher_number}** — ₹{gross:,.0f}  ·  _{tag}_")
            st.caption(
                f"{acc._fmt_date(v.voucher_date)} | Customer: "
                f"{customer_name}{order_ref}"
            )
            if v.description:
                st.caption(v.description)
            if st.button("Edit", key=f"{edit_prefix}_{v.id}",
                         use_container_width=True):
                acc._clear_other_invoice_dialog_flags(flag_key)
                st.session_state[flag_key] = v.id
                st.rerun()

    render_card_grid(page_vouchers, _render, suffix="invoices")


def render(services: dict):
    accounting_service = services["accounting"]
    actions = st.columns(2)
    if actions[0].button("+ Record Customization Invoice", type="primary",
                         key="btn_rec_cust_inv", use_container_width=True):
        acc._clear_other_invoice_dialog_flags(acc.INV_CUST)
        acc._customization_invoice_dialog(accounting_service)
    if actions[1].button("+ Record Sales Invoice", type="primary",
                         key="btn_rec_sales_inv", use_container_width=True):
        acc._clear_other_invoice_dialog_flags(acc.INV_SALES)
        acc._sales_invoice_dialog(accounting_service)

    render_list(
        ACCOUNTING_INVOICES,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        count_label="invoices",
        empty_text="No invoices recorded yet.",
    )
    acc.open_pending_dialogs(services)
