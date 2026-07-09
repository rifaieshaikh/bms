"""Accounting Invoices route (customization + sales invoices)."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.list_view import render_list
from vaybooks.bms.ui.components.voucher_card import VoucherEditAction, voucher_cards
from vaybooks.bms.ui.list_schemas import ACCOUNTING_INVOICES
from vaybooks.bms.ui.pages import accounts as acc


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
    def _builder(v):
        is_customization = v.voucher_type == VoucherType.CUSTOMIZATION_INVOICE
        flag_key = acc.INV_CUST if is_customization else acc.INV_SALES
        edit_prefix = "edit_cust_inv" if is_customization else "edit_sales_inv"
        return {
            "edit": VoucherEditAction(
                flag_key=flag_key,
                button_key=f"{edit_prefix}_{v.id}",
                before_edit=lambda fk=flag_key: acc._clear_other_invoice_dialog_flags(
                    fk
                ),
                clear_dialogs=True,
                register_dialog=True,
            ),
        }

    voucher_cards(page_vouchers, suffix="invoices", card_builder=_builder)


def render(services: dict):
    accounting_service = services["accounting"]
    if st.button(
        "+ Record Sales Invoice",
        type="primary",
        key="btn_rec_sales_inv",
        use_container_width=True,
    ):
        acc._clear_other_invoice_dialog_flags(acc.INV_SALES)
        acc._sales_invoice_dialog(services)

    render_list(
        ACCOUNTING_INVOICES,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        count_label="invoices",
        empty_text="No invoices recorded yet.",
    )
    acc.open_pending_dialogs(services)
