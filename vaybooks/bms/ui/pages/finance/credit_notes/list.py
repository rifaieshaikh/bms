"""Credit notes route."""

import streamlit as st

from vaybooks.bms.domain.shared.enums import VoucherType
from vaybooks.bms.ui.components.common.list_view import render_list
from vaybooks.bms.ui.components.common.voucher_card import voucher_cards
from vaybooks.bms.ui.dialog_utils import clear_all_dialog_flags
from vaybooks.bms.ui.list_schemas import CREDIT_NOTES
from vaybooks.bms.ui.pages.finance.accounts import list as acc


def _load(services, filters, sort):
    try:
        return services["accounting"].list_vouchers_by_type(VoucherType.CREDIT_NOTE)
    except Exception:
        return []


def _cards(page_vouchers, services):
    voucher_cards(page_vouchers, suffix="credit_notes", show_type_badge=False)


def render(services: dict):
    bar = render_list(
        CREDIT_NOTES,
        services=services,
        load_fn=_load,
        card_renderer=_cards,
        primary_label="+ Create Credit Note",
        primary_key="credit_notes_create_btn",
        count_label="credit notes",
        empty_text="No credit notes recorded yet.",
        page_key_nav="credit_notes_list",
    )
    if bar["primary_clicked"]:
        clear_all_dialog_flags()
        acc._credit_note_dialog(services["accounting"])
    acc.open_pending_dialogs(services)
