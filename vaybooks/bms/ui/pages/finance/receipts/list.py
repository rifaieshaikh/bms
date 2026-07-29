"""Receipts route."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.common.voucher_card import VoucherEditAction, voucher_cards
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags
from vaybooks.bms.ui.list_schemas import RECEIPTS
from vaybooks.bms.ui.pages.finance.accounts import list as acc


def _load(services, filters, sort):
    try:
        from vaybooks.bms.domain.identity.location_access import location_id_mongo_filter
        from vaybooks.bms.ui.auth.session import working_location_list_context

        working, accessible = working_location_list_context(services)
        filt = location_id_mongo_filter(working, accessible)
        return services["accounting"].list_vouchers_by_type(
            VoucherType.RECEIPT, location_filter=filt
        )
    except Exception:
        return []


def _cards(page_vouchers, services):
    def _edit(v):
        return {
            "edit": VoucherEditAction(
                flag_key=acc.RCPT,
                button_key=f"edit_rcpt_{v.id}",
            )
        }

    voucher_cards(
        page_vouchers,
        suffix="receipts",
        show_type_badge=False,
        card_builder=_edit,
    )


def render(services: dict):
    bar = render_list(
        RECEIPTS,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        primary_label="+ Record Receipt",
        primary_key="receipts_create_btn",
        count_label="receipts",
        empty_text="No receipts recorded yet.",
        page_key_nav="receipts_list",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        acc._receipt_dialog(services)
    acc.open_pending_dialogs(services)
