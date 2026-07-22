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
        if v.voucher_type != VoucherType.CUSTOMIZATION_INVOICE:
            return {}
        return {
            "edit": VoucherEditAction(
                flag_key=acc.INV_CUST,
                button_key=f"edit_cust_inv_{v.id}",
                before_edit=lambda: acc._clear_other_invoice_dialog_flags(acc.INV_CUST),
                clear_dialogs=True,
                register_dialog=True,
            ),
        }

    voucher_cards(page_vouchers, suffix="invoices", card_builder=_builder)


def render(services: dict):
    render_list(
        ACCOUNTING_INVOICES,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        count_label="invoices",
        empty_text="No invoices recorded yet.",
        page_key_nav="accounting_invoices_list",
    )
    acc.open_pending_dialogs(services)
